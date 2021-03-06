import datetime
import os
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import textwrap
import sys

from peewee import *
from pwiz import *

from .base import ModelTestCase
from .base import TestModel
from .base import db_loader
from .base import mock
from .base import skip_case_if


db = db_loader('sqlite')


class User(TestModel):
    username = CharField(primary_key=True)
    id = IntegerField(default=0)


class Note(TestModel):
    user = ForeignKeyField(User)
    text = TextField(index=True)
    data = IntegerField(default=0)
    misc = IntegerField(default=0)

    class Meta:
        indexes = (
            (('user', 'text'), True),
            (('user', 'data', 'misc'), False),
        )


class Category(TestModel):
    name = CharField(unique=True)
    parent = ForeignKeyField('self', null=True)


class OddColumnNames(TestModel):
    spaces = CharField(column_name='s p aces')
    symbols = CharField(column_name='w/-nug!')


class capture_output(object):
    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = self._buffer = StringIO()
        return self

    def __exit__(self, *args):
        self.data = self._buffer.getvalue()
        sys.stdout = self._stdout


EXPECTED = """
from peewee import *

database = SqliteDatabase('peewee_test.db', **{})

class UnknownField(object):
    def __init__(self, *_, **__): pass

class BaseModel(Model):
    class Meta:
        database = database

class Category(BaseModel):
    name = CharField(unique=True)
    parent = ForeignKeyField(column_name='parent_id', field='id', model='self', null=True)

    class Meta:
        table_name = 'category'

class User(BaseModel):
    id = IntegerField()
    username = CharField(primary_key=True)

    class Meta:
        table_name = 'user'

class Note(BaseModel):
    data = IntegerField()
    misc = IntegerField()
    text = TextField(index=True)
    user = ForeignKeyField(column_name='user_id', field='username', model=User)

    class Meta:
        table_name = 'note'
        indexes = (
            (('user', 'data', 'misc'), False),
            (('user', 'text'), True),
        )
""".strip()

EXPECTED_ORDERED = """
from peewee import *

database = SqliteDatabase('peewee_test.db', **{})

class UnknownField(object):
    def __init__(self, *_, **__): pass

class BaseModel(Model):
    class Meta:
        database = database

class User(BaseModel):
    username = CharField(primary_key=True)
    id = IntegerField()

    class Meta:
        table_name = 'user'

class Note(BaseModel):
    user = ForeignKeyField(column_name='user_id', field='username', model=User)
    text = TextField(index=True)
    data = IntegerField()
    misc = IntegerField()

    class Meta:
        table_name = 'note'
        indexes = (
            (('user', 'data', 'misc'), False),
            (('user', 'text'), True),
        )
""".strip()


class BasePwizTestCase(ModelTestCase):
    database = db
    requires = []

    def setUp(self):
        if not self.database.is_closed():
            self.database.close()
        if os.path.exists(self.database.database):
            os.unlink(self.database.database)

        super(BasePwizTestCase, self).setUp()
        self.introspector = Introspector.from_database(self.database)


class TestPwiz(BasePwizTestCase):
    requires = [User, Note, Category]

    def test_print_models(self):
        with capture_output() as output:
            print_models(self.introspector)

        self.assertEqual(output.data.strip(), EXPECTED)

    def test_print_header(self):
        cmdline = '-i -e sqlite %s' % db.database

        with capture_output() as output:
            with mock.patch('pwiz.datetime.datetime') as mock_datetime:
                now = mock_datetime.now.return_value
                now.strftime.return_value = 'February 03, 2015 15:30PM'
                print_header(cmdline, self.introspector)

        self.assertEqual(output.data.strip(), (
            '# Code generated by:\n'
            '# python -m pwiz %s\n'
            '# Date: February 03, 2015 15:30PM\n'
            '# Database: %s\n'
            '# Peewee version: %s') % (cmdline, db.database, peewee_version))


@skip_case_if(lambda: sys.version_info[:2] < (2, 7))
class TestPwizOrdered(BasePwizTestCase):
    requires = [User, Note]

    def test_ordered_columns(self):
        with capture_output() as output:
            print_models(self.introspector, preserve_order=True)

        self.assertEqual(output.data.strip(), EXPECTED_ORDERED)


class TestPwizInvalidColumns(BasePwizTestCase):
    requires = [OddColumnNames]

    def test_invalid_columns(self):
        with capture_output() as output:
            print_models(self.introspector)

        result = output.data.strip()
        expected = textwrap.dedent("""
            class Oddcolumnnames(BaseModel):
                s_p_aces = CharField(column_name='s p aces')
                w_nug_ = CharField(column_name='w/-nug!')

                class Meta:
                    table_name = 'oddcolumnnames'""").strip()

        actual = result[-len(expected):]
        self.assertEqual(actual, expected)
