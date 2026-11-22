import argparse
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import migrate

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('migrate','serve','worker'):
        sub = commands.add_parser(command)
        if command == 'serve':
            sub.add_argument('--frontend-dir')
    legacy = commands.add_parser('import-legacy', help='Explicitly import an existing local legacy SQLite workspace')
    legacy.add_argument('--source', required=True)
    legacy.add_argument('--owner-email', required=True, help='An existing Python account to receive owner access')
    legacy.add_argument('--dry-run', action='store_true', help='Validate and report without migrations or writes')
    args = parser.parse_args()
    settings = Settings()
    if args.command == 'serve' and args.frontend_dir:
        settings.frontend_dir = args.frontend_dir
    if args.command == 'migrate': migrate(settings)
    elif args.command == 'import-legacy':
        import json
        from sqlalchemy.exc import SQLAlchemyError
        from workpal_backend.infrastructure.database import Database
        from workpal_backend.legacy_import import import_legacy
        db = Database(settings)
        try:
            result = import_legacy(db.engine, args.source, args.owner_email, dry_run=args.dry_run)
        except ValueError as exc:
            parser.error(str(exc))
        except SQLAlchemyError:
            parser.error('Legacy import failed; its transaction was rolled back')
        finally:
            db.close()
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.command == 'serve':
        import uvicorn
        from workpal_backend.app import create_app
        uvicorn.run(create_app(settings),host=settings.host,port=settings.port,ws="workpal_backend.realtime.transport:RelayWebSocketProtocol")
    else:
        from workpal_backend.worker import run
        run(settings)
if __name__ == '__main__': main()
