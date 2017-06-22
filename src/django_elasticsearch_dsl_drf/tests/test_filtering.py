from __future__ import absolute_import

import unittest
import uuid

from django.core.management import call_command

from nine.versions import DJANGO_GTE_1_10

import pytest

from rest_framework import status

from books import constants
import factories

from .base import BaseRestFrameworkTestCase

if DJANGO_GTE_1_10:
    from django.urls import reverse
else:
    from django.core.urlresolvers import reverse

__title__ = 'django_elasticsearch_dsl_drf.tests.test_filtering'
__author__ = 'Artur Barseghyan <artur.barseghyan@gmail.com>'
__copyright__ = '2016-2017 Artur Barseghyan'
__license__ = 'GPL 2.0/LGPL 2.1'
__all__ = (
    'TestFiltering',
)


@pytest.mark.django_db
class TestFiltering(BaseRestFrameworkTestCase):
    """Test filtering."""

    pytestmark = pytest.mark.django_db

    @classmethod
    def setUpClass(cls):
        """Set up."""
        # Counts are primarily taken into consideration. Don't create Book
        # objects without `state`. If you don't know which state to use, use
        # ``constants.BOOK_PUBLISHING_STATUS_REJECTED``.
        cls.published_count = 10
        cls.published = factories.BookFactory.create_batch(
            cls.published_count,
            **{
                'state': constants.BOOK_PUBLISHING_STATUS_PUBLISHED,
            }
        )

        cls.in_progress_count = 10
        cls.in_progress = factories.BookFactory.create_batch(
            cls.in_progress_count,
            **{
                'state': constants.BOOK_PUBLISHING_STATUS_IN_PROGRESS,
            }
        )

        cls.prefix_count = 2
        cls.prefix = 'DelusionalInsanity'
        cls.prefixed = factories.BookFactory.create_batch(
            cls.prefix_count,
            **{

                'title': '{} {}'.format(cls.prefix, uuid.uuid4()),
                'state': constants.BOOK_PUBLISHING_STATUS_REJECTED,
            }
        )

        cls.no_tags_count = 5
        cls.no_tags = factories.BookWithoutTagsFactory.create_batch(
            cls.no_tags_count,
            **{
                'state': constants.BOOK_PUBLISHING_STATUS_REJECTED,
            }
        )

        cls.all_count = (
            cls.published_count +
            cls.in_progress_count +
            cls.prefix_count +
            cls.no_tags_count
        )

        cls.base_url = reverse('bookdocument-list', kwargs={})
        cls.base_publisher_url = reverse('publisherdocument-list', kwargs={})
        call_command('search_index', '--rebuild', '-f')

    def _field_filter_value(self, field_name, value, count):
        """Field filter value.

        Usage example:

            >>> self._field_filter_value(
            >>>     'title__wildcard',
            >>>     self.prefix[3:-3],
            >>>     self.prefix_count
            >>> )
        """
        url = self.base_url[:]
        data = {}
        response = self.client.get(
            url + '?{}={}'.format(field_name, value),
            data
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data['results']),
            count
        )

    def _field_filter_term(self, field_name, filter_value):
        """Field filter term.

        Example:

            http://localhost:8000/api/articles/?tags=children
        """
        self.authenticate()

        url = self.base_url[:]
        data = {}

        # Should contain 22 results
        response = self.client.get(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), self.all_count)

        # Should contain only 10 results
        filtered_response = self.client.get(
            url + '?{}={}'.format(field_name, filter_value),
            data
        )
        self.assertEqual(filtered_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(filtered_response.data['results']),
            self.published_count
        )

    def test_field_filter_term(self):
        """Field filter term."""
        return self._field_filter_term(
            'state',
            constants.BOOK_PUBLISHING_STATUS_PUBLISHED
        )

    def test_field_filter_term_explicit(self):
        """Field filter term."""
        return self._field_filter_term(
            'state__term',
            constants.BOOK_PUBLISHING_STATUS_PUBLISHED
        )

    def test_field_filter_range(self):
        """Field filter range.

        Example:

            http://localhost:8000/api/users/?age__range=16|67
        """
        lower_id = self.published[0].id
        upper_id = self.published[-1].id
        value = '{}|{}'.format(lower_id, upper_id)
        return self._field_filter_value(
            'id__range',
            value,
            self.published_count
        )

    def test_field_filter_range_with_boost(self):
        """Field filter range.

        Example:

            http://localhost:8000/api/users/?age__range=16|67|2.0
        """
        lower_id = self.published[0].id
        upper_id = self.published[-1].id
        value = '{}|{}|{}'.format(lower_id, upper_id, '2.0')
        return self._field_filter_value(
            'id__range',
            value,
            self.published_count
        )

    def test_field_filter_prefix(self):
        """Test filter prefix.

        Example:

            http://localhost:8000/api/articles/?tags__prefix=bio
        """
        return self._field_filter_value(
            'title__prefix',
            self.prefix,
            self.prefix_count
        )

    def test_field_filter_in(self):
        """Test filter in.

        Example:

            http://localhost:8000/api/articles/?id__in=1|2|3
        """
        return self._field_filter_value(
            'id__in',
            '|'.join([str(__b.id) for __b in self.prefixed]),
            self.prefix_count
        )

    def _field_filter_terms_list(self, field_name, in_values, count):
        """Field filter terms.

        Example:

            http://localhost:8000/api/articles/?id=1&id=2&id=3
        """
        url = self.base_url[:]
        data = {}
        url_parts = ['{}={}'.format(field_name, val) for val in in_values]
        response = self.client.get(
            url + '?{}'.format('&'.join(url_parts)),
            data
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data['results']),
            count
        )

    def test_field_filter_terms_list(self):
        """Test filter terms."""
        return self._field_filter_terms_list(
            'id',
            [str(__b.id) for __b in self.prefixed],
            self.prefix_count
        )

    def test_field_filter_terms_string(self):
        """Test filter terms.

        Example:

            http://localhost:8000/api/articles/?id__terms=1|2|3
        """
        return self._field_filter_value(
            'id__terms',
            '|'.join([str(__b.id) for __b in self.prefixed]),
            self.prefix_count
        )

    def _field_filter_exists(self, field_name, count):
        """Field filter exists.

        Example:

            http://localhost:8000/api/articles/?tags__exists=true
        """
        url = self.base_publisher_url[:]
        data = {}
        response = self.client.get(
            url + '?{}=true'.format(field_name),
            data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data['results']),
            count
        )

    # def test_field_filter_exists(self):
    #     """Test filter exists."""
    #     return self._field_filter_exists(
    #         'tags__exists',
    #         self.all_count - self.no_tags_count
    #     )

    def test_field_filter_wildcard(self):
        """Test filter wildcard.

        Example:

            http://localhost:8000/api/articles/?title__wildcard=*elusional*
        """
        return self._field_filter_value(
            'title__wildcard',
            '*{}*'.format(self.prefix[1:6]),
            self.prefix_count
        )

    def test_field_filter_exclude(self):
        """Test filter exclude.

        Example:

            http://localhost:8000/api/articles/?tags__exclude=children
        """
        return self._field_filter_value(
            'state__exclude',
            constants.BOOK_PUBLISHING_STATUS_PUBLISHED,
            self.all_count - self.published_count
        )


if __name__ == '__main__':
    unittest.main()
