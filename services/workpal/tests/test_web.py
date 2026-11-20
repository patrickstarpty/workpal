from django.test import SimpleTestCase, Client

class WebTests(SimpleTestCase):
    def test_shell_and_assets(self):
        for url, mime in [('/', 'text/html'), ('/app-assets/app.js', 'text/javascript'), ('/app-assets/client.js', 'text/javascript'), ('/app-assets/ui.js', 'text/javascript'), ('/app-assets/features/workspace.js', 'text/javascript'), ('/app-assets/features/projects.js', 'text/javascript'), ('/app-assets/features/issue-status-history.js', 'text/javascript'), ('/app-assets/features/issue-transition.js', 'text/javascript'), ('/app-assets/features/issue-parent.js', 'text/javascript'), ('/app-assets/features/issue-hierarchy.js', 'text/javascript'), ('/app-assets/features/issue-dependencies.js', 'text/javascript'), ('/app-assets/features/issues.js', 'text/javascript'), ('/app-assets/features/issue-create.js', 'text/javascript'), ('/app-assets/features/requirements-form.js', 'text/javascript'), ('/app-assets/features/issue-edit.js', 'text/javascript'), ('/app-assets/features/issue-archive.js', 'text/javascript'), ('/app-assets/styles.css', 'text/css'), ('/app-assets/inter.woff2', 'font/woff2'), ('/app-assets/mark.svg', 'image/svg+xml')]:
            with self.subTest(url=url):
                r=self.client.get(url)
                self.assertEqual(r.status_code,200)
                self.assertTrue(r['Content-Type'].startswith(mime))
                self.assertEqual(r['Cache-Control'],'no-store')
                self.assertEqual(r['X-Content-Type-Options'],'nosniff')
                self.assertIn("script-src 'self'",r['Content-Security-Policy'])
                self.assertNotIn('unsafe-inline',r['Content-Security-Policy'])
                self.assertEqual(self.client.head(url).content,b'')

    def test_paths_host_and_methods(self):
        for path in ['/app-assets/../client.js','/app-assets/%2e%2e/client.js','/app-assets/%252e%252e/client.js','/app-assets/config/settings.py','/app-assets/missing','/app-assets//app.js']:
            self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.client.get('/',HTTP_HOST='evil.invalid').status_code,400)
        # CSRF bypass here deliberately tests method dispatch, not CSRF policy.
        for path in ['/','/app-assets/app.js']:
            self.assertEqual(self.client.post(path).status_code,405)
        self.assertEqual(Client(enforce_csrf_checks=True).post('/api/v1/auth/login',{},content_type='application/json').status_code,403)
