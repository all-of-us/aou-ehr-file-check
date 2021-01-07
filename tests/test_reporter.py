import settings
import unittest
import omop_file_validator


class TestReporter(unittest.TestCase):
    # Checks if individual fields are as expected
    def check_error(self, e, message, actual, column_name=None, expected=None):
        self.assertEqual(e['message'], message)
        self.assertEqual(e['actual'], actual)
        if expected is not None:
            self.assertEqual(e['expected'], expected)
        if column_name is not None:
            self.assertEqual(e['column_name'], column_name)

    # "condition.csv" is an erroneous filename since it is not in line with the specifications under
    # [resources/omop](https://github.com/all-of-us/aou-ehr-file-check/tree/master/resources/omop)
    def check_invalid_table_name(self, f_name, e):
        self.assertEquals(f_name, 'condition.csv')
        self.check_error(e,
                         message=omop_file_validator.MSG_CANNOT_PARSE_FILENAME,
                         actual=f_name)

    # "drug_exposure.csv" has the column "person_id" missing
    def check_missing_column(self, f_name, e):
        self.assertEquals(f_name, 'drug_exposure.csv')
        self.check_error(e,
                         message=omop_file_validator.MSG_MISSING_HEADER,
                         actual="person_id")

    # "drug_exposure.csv" has the column "drug_id" added but it is not in the specifications under
    # [resources/omop/dose_era.json](https://github.com/all-of-us/aou-ehr-file-check/tree/master/resources/omop/dose_era.json)
    def check_incorrect_column(self, f_name, e):
        self.assertEquals(f_name, 'drug_exposure.csv')
        self.check_error(e,
                         message=omop_file_validator.MSG_INCORRECT_HEADER,
                         actual="drug_id")

    # "person.csv" has the columns "birth_datetime" and "day_of_birth" interchanged
    def check_incorrect_order(self, f_name, e):
        self.assertEquals(f_name, 'person.csv')
        self.check_error(e,
                         message=omop_file_validator.MSG_INCORRECT_ORDER,
                         actual="birth_datetime",
                         expected="day_of_birth")

    # "observation.csv" has an incorrect data type in the column "observation_type_concept_id" and
    # row 2 (line number 3), with "string" ("unknown") instead of "integer"
    def check_invalid_type(self, f_name, e):
        self.assertEquals(f_name, 'observation.csv')
        error_row_index = 2
        self.check_error(e,
                         message=omop_file_validator.MSG_INVALID_TYPE+" line number "+str(error_row_index+1),
                         actual="unknown",
                         column_name="observation_type_concept_id",
                         expected="integer")

    # "measurement.csv" has "person_id" as NULL in row 3 (line number 4) but it is a required value
    def check_required_value(self, f_name, e):
        self.assertEquals(f_name, 'measurement.csv')
        self.check_error(e,
                         message=omop_file_validator.MSG_NULL_DISALLOWED,
                         actual="",
                         column_name="person_id")

    # "observation.csv" has has invalid date formats in rows 4 and 5
    def check_invalid_date(self, f_name, e):
        self.assertEqual(f_name, 'observation.csv')
        self.assertEqual(
            e['message'],
            'Invalid date format. Expecting "YYYY-MM-DD": line numbers (4,5)')
        self.assertEqual(e['column_name'], 'observation_date')

    # "observation.csv" has has invalid date formats in rows 1, 3, and 5
    def check_invalid_timestamp(self, f_name, e):
        self.assertEqual(f_name, 'observation.csv')
        self.assertEqual(
            e['message'],
            'Invalid timestamp format. Expecting "YYYY-MM-DD hh:mm:ss": line numbers (1,3,5)'
        )
        self.assertEqual(e['column_name'], 'observation_datetime')

    # function to run the above tests
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
            self.check_invalid_type(f_name, error_map[f_name][2])

        self.check_invalid_date(f_name, error_map[f_name][0])
        self.check_invalid_timestamp(f_name, error_map[f_name][1])

        f_name = "measurement.csv"
        if self.assertIn("measurement.csv", error_map):
            self.check_required_value(f_name, error_map[f_name][0])

            
if __name__ == '__main__':
    unittest.main()
