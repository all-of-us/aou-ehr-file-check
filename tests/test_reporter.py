import settings
import unittest
import omop_file_validator
import pandas as pd
from pathlib import Path


class TestReporter(unittest.TestCase):
    # Checks if individual fields are as expected
    def check_error(self,
                    errors,
                    message,
                    actual=None,
                    column_name=None,
                    expected=None):
        all_messages = [e['message'] for e in errors]
        self.assertIn(message, all_messages)

        message_index = all_messages.index(message)

        if actual is not None:
            self.assertEqual(errors[message_index]['actual'], actual)
        if expected is not None:
            self.assertEqual(errors[message_index]['expected'], expected)
        if column_name is not None:
            self.assertEqual(errors[message_index]['column_name'], column_name)

    def check_invalid_table_name(self, errors, f_name):
        self.check_error(
            errors, message=f'"{Path(f_name).stem}" is not a valid OMOP table')

    def check_incorrect_column(self, errors, line_number=None, actual=None):
        message = omop_file_validator.MSG_INCORRECT_HEADER if line_number is None else f'{omop_file_validator.MSG_INCORRECT_HEADER}: line number {line_number}'
        self.check_error(errors, message=message, actual=actual)

    def check_missing_column(self,
                             errors,
                             line_number=None,
                             column_name=None,
                             expected=None):
        message = omop_file_validator.MSG_MISSING_HEADER if line_number is None else f'{omop_file_validator.MSG_MISSING_HEADER}: line number {line_number}'
        self.check_error(errors,
                         message=message,
                         column_name=column_name,
                         expected=expected)

    def check_incorrect_order(self, errors, actual=None, expected=None):
        self.check_error(errors,
                         message=omop_file_validator.MSG_INCORRECT_ORDER,
                         actual=actual,
                         expected=expected)

    def check_invalid_type(self,
                           errors,
                           linenumber=None,
                           actual=None,
                           column_name=None,
                           expected=None):
        error_row_index = 2
        self.check_error(errors,
                         message=omop_file_validator.MSG_INVALID_TYPE +
                         " line number " + str(linenumber),
                         actual=actual,
                         column_name=column_name,
                         expected=expected)

    def check_invalid_date(self, errors, column_name=None, linenumber=None):
        self.check_error(
            errors,
            message=
            f'Invalid date format. Expecting "YYYY-MM-DD": line number {linenumber}',
            column_name=column_name)

    def check_invalid_timestamp(self,
                                errors,
                                column_name=None,
                                linenumber=None):
        self.check_error(
            errors,
            message=
            f'Invalid timestamp format. Expecting "YYYY-MM-DD HH:MM:SS[.SSSSSS]": line number {linenumber}',
            column_name=column_name)

    def check_required_value(self,
                             errors,
                             line_number=None,
                             actual=None,
                             column_name=None):
        message = omop_file_validator.MSG_NULL_DISALLOWED if line_number is None else f'{omop_file_validator.MSG_NULL_DISALLOWED}: line number {line_number}'
        self.check_error(errors,
                         message=message,
                         actual=actual,
                         column_name=column_name)

    # function to run the above tests
    def test_error_list(self):
        submission_folder = settings.example_path
        error_map = omop_file_validator.evaluate_submission(submission_folder)

        # "condition.csv" is an erroneous filename since it is not in line with the specifications under
        # [resources/omop](https://github.com/all-of-us/aou-ehr-file-check/tree/master/resources/omop)
        f_name = "condition.csv"
        self.assertIn(f_name, error_map)
        self.check_invalid_table_name(error_map[f_name], f_name)

        # "drug_exposure.csv" has the column "drug_id" added but it is not in the specifications under
        # [resources/omop/dose_era.json](https://github.com/all-of-us/aou-ehr-file-check/tree/master/resources/omop/dose_era.json)
        f_name = "drug_exposure.csv"
        self.assertIn(f_name, error_map)
        self.check_incorrect_column(error_map[f_name], actual='drug_id')

        # "drug_exposure.csv" has the column "person_id" missing
        self.check_missing_column(error_map[f_name], column_name='person_id')

        # "person.csv" has the columns "birth_datetime" and "day_of_birth" interchanged
        f_name = "person.csv"
        self.assertIn(f_name, error_map)
        self.check_incorrect_order(error_map[f_name],
                                   actual="birth_datetime",
                                   expected="day_of_birth")

        # "observation.csv" has an incorrect data type in the column "observation_type_concept_id" and
        # row 2 (line number 3), with "string" ("unknown") instead of "integer"
        f_name = "observation.csv"
        self.assertIn(f_name, error_map)
        self.check_invalid_type(error_map[f_name],
                                linenumber=3,
                                actual="unknown",
                                column_name="observation_type_concept_id",
                                expected="integer")

        # "observation.csv" has has invalid date formats in row 5
        self.check_invalid_date(error_map[f_name],
                                column_name='observation_date',
                                linenumber=5)

        # "observation.csv" has has invalid timestamp formats in rows 1, 3, and 5
        self.check_invalid_timestamp(error_map[f_name],
                                     column_name='observation_datetime',
                                     linenumber=3)

        # "measurement.csv" has "person_id" as NULL in row 3 (line number 4) but it is a required value
        f_name = "measurement.csv"
        self.assertIn(f_name, error_map)
        self.check_required_value(error_map[f_name], column_name='person_id')

        # "visit_detail.csv" has "visit_occurrence_id" as NULL in row 1 but it is a required value
        f_name = "visit_detail.csv"
        self.assertIn(f_name, error_map)
        self.check_required_value(error_map[f_name],
                                  column_name='visit_occurrence_id')

    def test_load_json(self):
        submission_folder = settings.example_path
        error_map = omop_file_validator.evaluate_submission(submission_folder)

        f_name = "note.jsonl"
        self.assertIn(f_name, error_map)

        self.check_incorrect_column(error_map[f_name],
                                    line_number=4,
                                    actual='favorite_note_id')

        self.check_missing_column(error_map[f_name],
                                  line_number=4,
                                  expected='note_type_concept_id')

    def test_str_columns(self):
        file_path = Path(
            "tests/resources/examples_erroneous/procedure_occurrence.csv")
        f = open(file_path, 'r')
        # get original data types
        original_df = pd.read_csv(f)
        original_dtypes = original_df.dtypes.to_dict()
        # reset file object to beginning of file
        f.seek(0)
        # run csv checks and get resulting datatypes
        result = omop_file_validator.run_csv_checks(file_path, f)
        enforced_dtypes = result['data_types']
        self.assertDictEqual(original_dtypes, enforced_dtypes)


if __name__ == '__main__':
    unittest.main()
