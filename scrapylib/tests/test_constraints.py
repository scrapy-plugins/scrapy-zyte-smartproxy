import unittest
from scrapylib.constraints import RequiredFields, IsType, IsNumber, IsPrice, MaxLen, MinLen


class RequiredFieldsTest(unittest.TestCase):

    def setUp(self):
        self.item = {'str': 'bar', 'list': ['one']}

    def test_basic(self):
        RequiredFields('str')(self.item)
        RequiredFields('str', 'list')(self.item)

    def test_fail(self):
        self.assertRaises(AssertionError, RequiredFields('list', 'xxx'), self.item)

class IsTypeTest(unittest.TestCase):

    def setUp(self):
        self.item = {'str': 'bar', 'list': ['one']}

    def test_ok(self):
        IsType(basestring, 'str')(self.item)
        IsType(list, 'list')(self.item)
        IsType(list, 'missing')(self.item)

    def test_fail(self):
        self.assertRaises(AssertionError, IsType(basestring, 'list'), self.item)
        self.assertRaises(AssertionError, IsType(list, 'str'), self.item)

class IsNumberTest(unittest.TestCase):

    def setUp(self):
        self.item = {'name': 'foo', 'age': '23'}

    def test_ok(self):
        IsNumber('age')(self.item)
        IsNumber('xxx')(self.item)

    def test_fail(self):
        self.assertRaises(AssertionError, IsNumber('name'), self.item)

class IsPriceTest(unittest.TestCase):

    def setUp(self):
        self.item = {'name': 'foo', 'price': '1,223.23 '}

    def test_basic(self):
        IsPrice('price')(self.item)
        IsPrice('xxx')(self.item)

    def test_fail(self):
        self.assertRaises(AssertionError, IsPrice('name'), self.item)

class MaxLenTest(unittest.TestCase):

    def setUp(self):
        self.item = {'name': 'foo', 'other': 'very long content'}

    def test_ok(self):
        MaxLen(8, 'name')(self.item)
        MaxLen(8, 'xxx')(self.item)

    def test_fail(self):
        self.assertRaises(AssertionError, MaxLen(8, 'other'), self.item)

class MinLenTest(MaxLenTest):

    def test_ok(self):
        MinLen(8, 'other')(self.item)
        MinLen(8, 'xxx')(self.item)

    def test_fail(self):
        self.assertRaises(AssertionError, MinLen(8, 'name'), self.item)
