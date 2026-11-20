import hashlib
from tests.support import WorkpalCase
from tests.access_support import AccessFixtures
from workpal.delivery import artifacts

class Publish(AccessFixtures, WorkpalCase):
    def test_registry_finish(self):
        u = artifacts.begin(self.actor, {'filename':'x','size':3})
        artifacts.append(self.actor,u['id'],0,b'abc')
        result = self.act(self.actor,'artifact.upload.finish',{'upload_id':u['id'],'sha256':hashlib.sha256(b'abc').hexdigest()},key='finish')
        self.assertEqual(result.data['size'],3)
