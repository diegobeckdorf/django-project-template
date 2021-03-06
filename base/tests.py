"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

# standard library

# django
from django.conf import settings
from django.contrib import admin
from django.urls import NoReverseMatch
from django.urls import resolve
from django.urls import reverse
from django.test import TestCase

# django-cron
from django_cron import get_class

# urls
from project.urls import urlpatterns

# utils
from inflection import underscore
from base.utils import get_our_models
from base.utils import random_string

# utils
from base.mockups import Mockup


class BaseTestCase(TestCase, Mockup):

    def setUp(self):
        super(BaseTestCase, self).setUp()

        self.password = random_string()
        self.user = self.create_user(self.password)

        self.login()

    def login(self, user=None, password=None):
        if user is None:
            user = self.user
            password = self.password

        return self.client.login(email=user.email, password=password)


def reverse_pattern(pattern, namespace, args=None, kwargs=None):
    try:
        if namespace:
            return reverse('{}:{}'.format(
                namespace, pattern.name, args=args, kwargs=kwargs)
            )
        else:
            return reverse(pattern.name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return None


class UrlsTest(BaseTestCase):

    def setUp(self):
        super(UrlsTest, self).setUp()

        # we are going to send parameters, so one thing we'll do is to send
        # tie id 1
        self.user.delete()
        self.user.id = 1

        # give the user all the permissions, so we test every page
        self.user.is_superuser = True

        self.user.save()
        self.login()

        self.default_params = {}

        for model in get_our_models():
            model_name = underscore(model.__name__)
            method_name = 'create_{}'.format(model_name)
            param_name = '{}_id'.format(model_name)

            obj = getattr(self, method_name)()

            self.assertIsNotNone(obj, '{} returns None'.format(method_name))

            self.default_params[param_name] = obj.id

    def reverse_pattern(self, pattern, namespace):
        url = reverse_pattern(pattern, namespace)

        if url is None:
            url = reverse_pattern(pattern, namespace, args=(1,))

            if url is None:
                url = reverse_pattern(pattern, namespace, args=(1, 1))

        if url is None:
            return None

        view_params = resolve(url).kwargs

        for param in view_params:
            try:
                view_params[param] = self.default_params[param]
            except KeyError:
                pass

        return reverse_pattern(pattern, namespace, kwargs=view_params)

    def test_responses(self):

        ignored_namespaces = [
            'admin',
        ]

        def test_url_patterns(patterns, namespace=''):

            if namespace in ignored_namespaces:
                return

            for pattern in patterns:
                self.login()

                if hasattr(pattern, 'name'):
                    url = self.reverse_pattern(pattern, namespace)

                    if not url:
                        continue

                    try:
                        response = self.client.get(url)
                    except Exception:
                        print("Url {} failed: ".format(url))
                        raise

                    msg = 'url "{}" returned {}'.format(
                        url, response.status_code
                    )
                    self.assertIn(
                        response.status_code,
                        (200, 302, 403, 405), msg
                    )
                else:
                    test_url_patterns(pattern.url_patterns, pattern.namespace)

        test_url_patterns(urlpatterns)

        for model, model_admin in admin.site._registry.items():
            patterns = model_admin.get_urls()
            test_url_patterns(patterns, namespace='admin')


class CheckErrorPages(TestCase):
    def test_404(self):
        response = self.client.get('/this-url-does-not-exist')
        self.assertTemplateUsed(response, 'exceptions/404.pug')


class CronTests(BaseTestCase):
    def test_cron_classes_to_run(self):
        """
        Asserts that a cron class name can be imported using the canonical name
        given in project settings
        """

        cron_class_names = getattr(settings, 'CRON_CLASSES', [])
        for cron_class_name in cron_class_names:
            assert get_class(cron_class_name)
