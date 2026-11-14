import sys
import decimal
import operator
from tests import unittest, OrderedDict

import jmespath
import jmespath.functions


class TestSearchOptions(unittest.TestCase):
    def test_can_provide_dict_cls(self):
        result = jmespath.search(
            '{a: a, b: b, c: c}.*',
            {'c': 'c', 'b': 'b', 'a': 'a', 'd': 'd'},
            options=jmespath.Options(dict_cls=OrderedDict))
        self.assertEqual(result, ['a', 'b', 'c'])

    def test_can_provide_custom_functions(self):
        class CustomFunctions(jmespath.functions.Functions):
            @jmespath.functions.signature(
                {'types': ['number']},
                {'types': ['number']})
            def _func_custom_add(self, x, y):
                return x + y

            @jmespath.functions.signature(
                {'types': ['number']},
                {'types': ['number']})
            def _func_my_subtract(self, x, y):
                return x - y


        options = jmespath.Options(custom_functions=CustomFunctions())
        self.assertEqual(
            jmespath.search('custom_add(`1`, `2`)', {}, options=options),
            3
        )
        self.assertEqual(
            jmespath.search('my_subtract(`10`, `3`)', {}, options=options),
            7
        )
        # Should still be able to use the original functions without
        # any interference from the CustomFunctions class.
        self.assertEqual(
            jmespath.search('length(`[1, 2]`)', {}), 2
        )



class TestPythonSpecificCases(unittest.TestCase):
    def test_can_compare_strings(self):
        # This is python specific behavior that's not in the official spec
        # yet, but this was regression from 0.9.0 so it's been added back.
        self.assertTrue(jmespath.search('a < b', {'a': '2016', 'b': '2017'}))

    @unittest.skipIf(not hasattr(sys, 'maxint'), 'Test requires long() type')
    def test_can_handle_long_ints(self):
        result = sys.maxint + 1
        self.assertEqual(jmespath.search('[?a >= `1`].a', [{'a': result}]),
                         [result])

    def test_can_handle_decimals_as_numeric_type(self):
        result = decimal.Decimal('3')
        self.assertEqual(jmespath.search('[?a >= `1`].a', [{'a': result}]),
                         [result])


class TestMixedTypeOrderingComparisons(unittest.TestCase):
    # Ordering comparisons between a number and a non-number (e.g. a
    # string) must yield None instead of raising the language's native
    # type comparison error.  This must hold both for top-level
    # comparisons and for comparisons inside filter projections.
    ORDERING_OPS = {
        '<': operator.lt,
        '>': operator.gt,
        '<=': operator.le,
        '>=': operator.ge,
    }

    def test_mixed_number_and_string_returns_none_top_level(self):
        for op in self.ORDERING_OPS:
            for expression in ('a %s b' % op, 'b %s a' % op):
                result = jmespath.search(
                    expression, {'a': 1, 'b': '2'})
                self.assertIsNone(
                    result,
                    'Expected None for %r, got %r' % (expression, result))

    def test_mixed_number_and_string_returns_none_in_filter(self):
        data = [{'a': 1, 'b': '2'}, {'a': 3, 'b': 4}]
        for op, op_func in self.ORDERING_OPS.items():
            for expression, left, right in (
                    ('[?a %s b].a' % op, 3, 4),
                    ('[?b %s a].a' % op, 4, 3)):
                result = jmespath.search(expression, data)
                # The mixed-type element yields None (falsy) and is
                # filtered out; the number/number element still compares.
                expected = [3] if op_func(left, right) else []
                self.assertEqual(
                    result, expected,
                    'Unexpected result for %r: %r' % (expression, result))

    def test_mixed_number_and_string_literal_returns_none(self):
        for op in self.ORDERING_OPS:
            for expression in ('a %s `1`' % op, '`1` %s a' % op):
                result = jmespath.search(expression, {'a': 'foo'})
                self.assertIsNone(
                    result,
                    'Expected None for %r, got %r' % (expression, result))

    def test_mixed_number_and_string_literal_in_filter(self):
        data = [{'a': 'foo'}, {'a': 2}]
        for op, op_func in self.ORDERING_OPS.items():
            for expression, left, right in (
                    ('[?a %s `1`].a' % op, 2, 1),
                    ('[?`1` %s a].a' % op, 1, 2)):
                result = jmespath.search(expression, data)
                expected = [2] if op_func(left, right) else []
                self.assertEqual(
                    result, expected,
                    'Unexpected result for %r: %r' % (expression, result))

    def test_string_string_comparison_still_works(self):
        for op, expected in (('<', True), ('>', False),
                             ('<=', True), ('>=', False)):
            self.assertEqual(
                jmespath.search('a %s b' % op,
                                {'a': '2016', 'b': '2017'}),
                expected)
        # Same behavior inside a filter projection.
        data = [{'a': '2016'}, {'a': '2018'}]
        self.assertEqual(
            jmespath.search('[?a < `"2017"`].a', data), ['2016'])

    def test_number_number_comparison_still_works(self):
        for op, expected in (('<', True), ('>', False),
                             ('<=', True), ('>=', False)):
            self.assertEqual(
                jmespath.search('a %s b' % op, {'a': 1, 'b': 2}), expected)
        self.assertEqual(
            jmespath.search('[?a >= `1`].a', [{'a': 1}, {'a': 0}]), [1])

    def test_bool_number_comparison_still_returns_none(self):
        # Pre-existing behavior: booleans are not comparable to numbers
        # and quietly yield None.  This must not regress.
        for op in self.ORDERING_OPS:
            for expression in ('a %s b' % op, 'b %s a' % op):
                self.assertIsNone(
                    jmespath.search(expression, {'a': True, 'b': 1}))
        data = [{'a': True}, {'a': 2}]
        for op, op_func in self.ORDERING_OPS.items():
            expected = [2] if op_func(2, 1) else []
            self.assertEqual(
                jmespath.search('[?a %s `1`].a' % op, data), expected)
