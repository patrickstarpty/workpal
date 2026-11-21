"""POSIX byte storage. Callers authorize reads and fence every lease in the ledger.

No metadata sniffing or ACLs. Failures retain evidence; never infer ledger commit
from an I/O result. Root must already exist and remain under trusted ownership.
"""
import hashlib
import os
from pathlib import Path
import re
import secrets
import stat


class StorageError(Exception):
    """Invalid path, unsupported platform, or failed storage operation."""


class SizeLimitExceeded(StorageError):
    pass


class StorageCollision(StorageError):
    pass


def _translate(exc):
    return StorageCollision(str(exc)) if isinstance(exc, FileExistsError) else StorageError(str(exc))


class LocalBlobStore:
    def __init__(self, root):
        self.root = Path(os.path.abspath(root))
        if not hasattr(os, 'O_NOFOLLOW') or os.open not in os.supports_dir_fd or os.link not in os.supports_dir_fd:
            raise StorageError('Secure dir_fd/no-follow storage is unsupported')
        with self._directory() as fd:
            self.identity = os.fstat(fd).st_dev, os.fstat(fd).st_ino

    @staticmethod
    def new_key():
        return secrets.token_hex(16)

    @staticmethod
    def _key(key):
        if not isinstance(key, str) or re.fullmatch('[0-9a-f]{32}', key) is None:
            raise StorageError('Malformed opaque key')
        return key

    def _name(self, key, lease=None):
        key = self._key(key)
        return key + '.ready' if lease is None else key + '.' + self._key(lease) + '.staging'

    from contextlib import contextmanager

    @contextmanager
    def _directory(self):
        fd = None
        try:
            fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
            for component in self.root.parts[1:]:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            info = os.fstat(fd)
            if hasattr(self, 'identity') and self.identity != (info.st_dev, info.st_ino):
                raise StorageError('Upload root replaced')
            yield fd
        except OSError as exc:
            raise _translate(exc) from exc
        finally:
            if fd is not None:
                os.close(fd)

    def _open(self, name, flags):
        with self._directory() as directory:
            fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise StorageError('Object is not a regular file')
                return os.fdopen(fd, 'wb' if flags & os.O_WRONLY else 'rb', buffering=0)
            except BaseException:
                os.close(fd)
                raise

    def create_staging(self, key, lease_token):
        name = self._name(key, lease_token)
        with self._directory() as directory:
            try:
                os.stat(self._name(key), dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise StorageCollision('Ready object already exists')
        return self._open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)

    def write_bounded(self, staging, stream, max_bytes):
        if max_bytes < 0:
            raise ValueError('max_bytes must be nonnegative')
        size, digest = 0, hashlib.sha256()
        try:
            while True:
                chunk = stream.read(min(65536, max_bytes - size + 1))
                if not chunk:
                    break
                if len(chunk) > max_bytes - size:
                    raise SizeLimitExceeded('Upload exceeds byte limit')
                view = memoryview(chunk)
                while view:
                    written = os.write(staging.fileno(), view)
                    if written <= 0:
                        raise StorageError('Write made no progress')
                    view = view[written:]
                size += len(chunk)
                digest.update(chunk)
            os.fsync(staging.fileno())
        except OSError as exc:
            raise _translate(exc) from exc
        return size, digest.hexdigest()

    def sync_and_promote(self, key, lease_token):
        staging, ready = self._name(key, lease_token), self._name(key)
        with self._directory() as directory:
            with self._open(staging, os.O_RDONLY) as source:
                os.fsync(source.fileno())
                current = os.stat(staging, dir_fd=directory, follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (os.fstat(source.fileno()).st_dev, os.fstat(source.fileno()).st_ino):
                    raise StorageError('Staging object replaced')
                # link is atomic, same-filesystem, and refuses an existing target.
                # Unlike rename(), it cannot overwrite a committed object.
                os.link(staging, ready, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
                os.fsync(directory)
                expected = os.fstat(source.fileno())
                for name in (ready, staging):
                    published = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if not stat.S_ISREG(published.st_mode) or (published.st_dev, published.st_ino) != (expected.st_dev, expected.st_ino):
                        # Leave both names as pending evidence for the fenced
                        # reconciler. Never report publication success here.
                        raise StorageError('Staging object replaced during publication')
                os.unlink(staging, dir_fd=directory)
                os.fsync(directory)

    def open_ready(self, key):
        """Caller MUST authorize and check ledger ready state before calling."""
        return self._open(self._name(key), os.O_RDONLY)

    def delete_owned(self, key, lease_token, *, ready=False):
        """Ledger must fence lease and authorize final deletion explicitly."""
        names = [self._name(key, lease_token)]
        if ready:
            names.append(self._name(key))
        with self._directory() as directory:
            for name in names:
                try:
                    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode):
                        raise StorageError('Refusing nonregular object cleanup')
                    os.unlink(name, dir_fd=directory)
                except FileNotFoundError:
                    pass
            os.fsync(directory)
