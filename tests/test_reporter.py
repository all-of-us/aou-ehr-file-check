import settings
import unittest
import omop_file_validator


class TestReporter(unittest.TestCase):
    def check_error(self, e, message, actual, column_name=None, expected=None):
        self.assertEqual(e['message'], message)
        self.assertEqual(e['actual'], actual)
        if expected is not None:
            self.assertEqual(e['expected'], expected)
        if column_name is not None:
            self.assertEqual(e['column_name'], column_name)

    def check_invalid_table_name(self, f_name, e):
        self.assertEquals(f_name, 'condition.csv')
        self.check_error(e,
                         message=omop_file_validator.MSG_CANNOT_PARSE_FILENAME,
                         actual=f_name)

    def check_missing_column(self, f_name, e):
        self.assertEquals(f_name, 'drug_exposure.csv')
        self.check_error(e,
                         message=omop_file_validator.MSG_MISSING_HEADER,
                         actual="person_id")

    def check_incorrect_column(self, f_name, e):
        self.assertEquals(f_name, 'drug_exposure.csv')
        self.check_error(e,
                         message=omop_file_validator.MSG_INCORRECT_HEADER,
                         actual="drug_id")

    def check_incorrect_order(self, f_name, e):
        self.assertEquals(f_name, 'person.csv')
        self.check_error(e,
                         message=omop_file_validator.MSG_INCORRECT_ORDER,
                         actual="birth_datetime",
                         expected="day_of_birth")

    def check_invalid_type(self, f_name, e):
        self.assertEquals(f_name, 'observation.csv')
        error_row_index = 2
        self.check_error(e,
                         message=omop_file_validator.MSG_INVALID_TYPE+" line number "+str(error_row_index+1),
                         actual="unknown",
                         column_name="observation_type_concept_id",
                         expected="integer")

    def check_required_value(self, f_name, e):
        self.assertEquals(f_name, 'measurement.csv')
        self.check_error(e,
                         message=omop_file_validator.MSG_NULL_DISALLOWED,
                         actual="",
                         column_name="person_id")

    def test_error_list(self):
        submission_folder = settings.example_path
        error_map = omop_file_validator.evaluate_submission(submission_folder)

        f_name = "condition.csv"
        if self.assertIn(f_name, error_map):
            self.check_invalid_table_name(f_name, error_map[f_name][0])

        f_name = "drug_exposure.csv"
        if self.assertIn("drug_exposure.csv", error_map):
            self.check_incorrect_column(f_name, error_map[f_name][0])
            self.check_missing_column(f_name, error_map[f_name][1])

        f_name = "person.csv"
        if self.assertIn("person.csv", error_map):
            self.check_incorrect_order(f_name, error_map[f_name][0])

        f_name = "observation.csv"
        if self.assertIn("observation.csv", error_map):
            self.check_invalid_type(f_name, error_map[f_name][0])

        f_name = "measurement.csv"
        if self.assertIn("measurement.csv", error_map):
            self.check_required_value(f_name, error_map[f_name][0])


if __name__ == '__main__':
    unittest.main()
