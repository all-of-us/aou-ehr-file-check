import settings
import unittest
import omop_file_validator
import os
import difflib


class TestReporter(unittest.TestCase):
    def assert_line_equality(self, first, second, msg=None):
        self.assertTrue(isinstance(first, str), 'First line is not a string')
        self.assertTrue(isinstance(second, str), 'Second line is not a string')
        if first != second:
            message = ''.join(difflib.ndiff(first.splitlines(True), second.splitlines(True)))
            if msg:
                message += " : " + msg
            self.fail("Lines are not the same:\n" + message)

    def assert_file_equality(self, f1, f2, msg=""):
        line_list1 = f1.readlines()
        line_list2 = f2.readlines()
        if len(line_list1) != len(line_list2):
            self.fail("Files are unequal:\n" + msg)
        else:
            for i in range(len(line_list1)):
                self.assert_line_equality(line_list1[i], line_list2[i])

    def test_against_file(self):
        submission_folder = settings.example_path
        omop_file_validator.evaluate_submission(submission_folder)

        output_folder = os.path.join(settings.example_path, 'errors')
        results_file = os.path.join(output_folder, 'results.csv')

        expected_results_file = os.path.join(submission_folder, 'expected_errors', 'results.csv')

        with open(results_file, 'r') as f1, open(expected_results_file) as f2:
            self.assert_file_equality(f1, f2)


if __name__ == '__main__':
    unittest.main()
