import glob
import traceback

import settings
import os
import codecs
import pandas as pd
import numpy as np
import csv
import json
import datetime
import collections
import re

RESULT_SUCCESS = 'success'
MSG_CANNOT_PARSE_FILENAME = 'Cannot parse filename'
MSG_INVALID_TYPE = 'Type mismatch'
MSG_INCORRECT_HEADER = 'Column not in table definition'
MSG_MISSING_HEADER = 'Column missing in file'
MSG_INCORRECT_ORDER = 'Column not in expected order'
MSG_NULL_DISALLOWED = 'NULL values are not allowed for column'
MSG_INVALID_DATE = 'Invalid date format. Expecting "YYYY-MM-DD"'
MSG_INVALID_TIMESTAMP = 'Invalid timestamp format. Expecting "YYYY-MM-DD HH:MM:SS[.SSSSSS]"'

HEADER_KEYS = ['file_name', 'table_name']
ERROR_KEYS = ['message', 'column_name', 'actual', 'expected']

VALID_DATE_FORMAT = ['%Y-%m-%d']

VALID_TIMESTAMP_FORMAT = ['%Y-%m-%d %H:%M',
 '%Y-%m-%d %H:%MZ',
 '%Y-%m-%d %H:%M %Z',
 '%Y-%m-%d %H:%M%z',
 '%Y-%m-%d %H:%M:%S',
 '%Y-%m-%d %H:%M:%SZ',
 '%Y-%m-%d %H:%M:%S %Z',
 '%Y-%m-%d %H:%M:%S%z',
 '%Y-%m-%d %H:%M:%S.%f',
 '%Y-%m-%d %H:%M:%S.%fZ',
 '%Y-%m-%d %H:%M:%S.%f %Z',
 '%Y-%m-%d %H:%M:%S.%f%z',
 '%Y-%m-%dT%H:%M',
 '%Y-%m-%dT%H:%MZ',
 '%Y-%m-%dT%H:%M %Z',
 '%Y-%m-%dT%H:%M%z',
 '%Y-%m-%dT%H:%M:%S',
 '%Y-%m-%dT%H:%M:%SZ',
 '%Y-%m-%dT%H:%M:%S %Z',
 '%Y-%m-%dT%H:%M:%S%z',
 '%Y-%m-%dT%H:%M:%S.%f',
 '%Y-%m-%dT%H:%M:%S.%fZ',
 '%Y-%m-%dT%H:%M:%S.%f %Z',
 '%Y-%m-%dT%H:%M:%S.%f%z']

SCIENTIFIC_NOTATION_REGEX = "^(?:-?\d*)\.?\d+[eE][-\+]?\d+$"

csv.register_dialect('load',
                     quotechar='"',
                     doublequote=True,
                     delimiter=',',
                     quoting=csv.QUOTE_ALL,
                     strict=True)


def get_readable_key(key):
    new_key = key.replace('_', ' ')
    new_key = new_key.title()
    return new_key


def get_cdm_table_columns(table_name):
    # allow files to be found regardless of CaSe
    file = os.path.join(settings.cdm_metadata_path,
                        table_name.lower() + '.json')
    if os.path.isfile(file):
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f, object_pairs_hook=collections.OrderedDict)
    else:
        return None


def type_eq(cdm_column_type, submission_column_type):
    """
    Compare column type in spec with column type in submission
    :param cdm_column_type:
    :param submission_column_type:
    :return:
    """
    if cdm_column_type == 'time':
        return submission_column_type == 'character varying'
    if cdm_column_type == 'integer':
        return submission_column_type == 'int'
    if cdm_column_type in ['character varying', 'text', 'string']:
        return submission_column_type in ('str', 'unicode', 'object')
    if cdm_column_type == 'date':
        return submission_column_type in ['str', 'unicode', 'datetime64[ns]']
    if cdm_column_type == 'timestamp':
        return submission_column_type in ['str', 'unicode', 'datetime64[ns]']
    if cdm_column_type in ['numeric', 'float']:
        return submission_column_type == 'float'
    else:
        print(submission_column_type)
        raise Exception('Unsupported CDM column type ' + cdm_column_type)


def cast_type(cdm_column_type, value):
    """
    Compare column type in spec with column type in submission
    :param cdm_column_type:
    :param value:
    :return:
    """
    if cdm_column_type in ('integer', 'int64'):
        # Regex check only relevant if submission dtype is 'object'
        if not re.match(SCIENTIFIC_NOTATION_REGEX, str(value)):
            return int(value)
    if cdm_column_type in ('character varying', 'text', 'string'):
        return str(value)
    if cdm_column_type == 'numeric':
        return float(value)
    if cdm_column_type == 'float' and isinstance(value, float):
        return value
    if cdm_column_type == 'date' and isinstance(value, datetime.date):
        return value
    if cdm_column_type == 'timestamp' and isinstance(
            value, datetime.datetime):  # do not do datetime.datetime
        return value


def date_format_valid(date_str, fmt='%Y-%m-%d'):
    """Check if a date string matches a certain pattern and is compilable into a datetime object

    :param date_str: 
    :type date_str: string
    :param fmt: A C standard-compliant date format, defaults to '%Y-%m-%d'
    :type fmt: str, optional
    :return: A boolean indicating if date string matches the date format
    :rtype: bool
    """

    try:
        #Avoids out of range dates, e.g. 2020-02-31
        datetime.datetime.strptime(date_str, fmt)
    except ValueError:
        return False

    return True


def detect_bom_encoding(file_path):
    default = None
    with open(file_path, 'rb') as f:
        buffer = f.read(4)
    non_standard_encodings = [
        ('utf-8-sig', (codecs.BOM_UTF8, )),
        ('utf-16', (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)),
        ('utf-32', (codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE))
    ]
    for enc, boms in non_standard_encodings:
        if any(buffer.startswith(bom) for bom in boms):
            print(
                'Detected non-standard encoding %s. Please encode the CSV file in utf-8 standard'
                % enc)
            return enc
    return default


# finds the first occurrence of an error for that column.
# currently, it does NOT find all errors in the column.
def find_error_in_file(column_name, cdm_column_type, submission_column_type,
                       df):
    for i, (index, row) in enumerate(df.iterrows()):

        try:
            if i <= len(df) - 1:
                if pd.notnull(row[column_name]):
                    cast_type(cdm_column_type, row[column_name])
            else:
                return False
        except ValueError:
            # print(row[column_name])
            return index


def find_blank_lines(f):
    """Check for rows in a csv file with only empty values

    :param f: A file object
    :type f: file-like object
    :return: List of rows with all empty values
    :rtype: list
    """
    df = pd.read_csv(f)
    indices = df.index[df.apply(
        lambda row: all(row.apply(lambda col: pd.isnull(col))),
        axis=1)].tolist()

    return [i + 1 for i in indices]


def find_scientific_notation_errors(f, int_columns):
    df = pd.read_csv(f, dtype=str)
    df = df.rename(columns=str.lower)
    df = df[[col for col in int_columns if col in df.columns]]

    errors = []
    sci_not_line = collections.defaultdict(int)

    for submission_col_name in df.columns:
        submission_column = df[submission_col_name]
        for i, value in submission_column.items():
            if pd.notnull(value) and re.match(SCIENTIFIC_NOTATION_REGEX,
                                              value):
                sci_not_line[submission_col_name] = (value, i + 1)
                break

    for col, (value, line_num) in sci_not_line.items():
        e = dict(message=(
            f"Scientific notation value '{value}' was found on line {line_num}. "
            "Scientific notation is not allowed for integer fields."),
                 column_name=col)
        errors.append(e)

    return errors


def check_csv_format(f, column_names):
    results = []
    idx = 1
    line = []
    header_error_msg = 'Please add/fix incorrect headers at the top of the file, enclosed in double quotes'
    quote_comma_error_msg = 'Stray double quote or comma within field on line %s'
    try:
        reader = csv.reader(f, dialect='load')
        header = next(reader)
        line = header
        if header != column_names:
            results.append([header_error_msg, header, column_names])
        for idx, line in enumerate(reader, start=2):
            for field in line:
                if '\n' in field:
                    newline_msg = 'Newline character found on line %s: %s\n' \
                                  'Please replace newline "\\n" characters with space " "' % (str(idx), line)
                    print(newline_msg)
                    results.append([newline_msg, None, None])
            if len(line) != len(column_names):
                column_mismatch_msg = 'Incorrect number of columns on line %s: %s' % (
                    str(idx), line)
                results.append([column_mismatch_msg, None, None])
    except (ValueError, csv.Error):
        print(traceback.format_exc())
        if not line:
            print(quote_comma_error_msg % (str(idx)))
            print(header_error_msg + '\n')
        else:
            print(quote_comma_error_msg % (str(idx + 1)))
            print('Previously parsed line %s: %s\n' % (str(idx), line))
        print(
            'Enclose all fields in double-quotes\n'
            'e.g. person_id,2020-05-05,6345 -> "person_id","2020-05-05","6345"\n'
            'At a minimum, enclose all non-numeric fields in double-quotes \n'
            'e.g. person_id,2020-05-05,6345 -> "person_id","2020-05-05",6345\n'
        )
        print(
            'Pair stray double quotes or remove them if they are inside a field \n'
            'e.g. "wound is 1" long" -> "wound is 1"" long" or "wound is 1 long"\n'
        )
        print(
            'Remove stray commas if they are inside a field and next to a double quote \n'
            'e.g. "drug route: "orally", "topically"" -> "drug route: ""orally"" ""topically"""\n'
        )
    f.seek(0)
    return results


def run_checks(file_path, f):
    file_name, file_extension = os.path.splitext(file_path)
    file_path_parts = file_name.split(os.sep)
    table_name = file_path_parts[-1]
    print('Found CSV file %s' % file_path)

    result = {
        'passed': False,
        'errors': [],
        'file_name': table_name + file_extension,
        'table_name': get_readable_key(table_name)
    }

    # get the column definitions for a particular OMOP table
    cdm_table_columns = get_cdm_table_columns(table_name)

    if cdm_table_columns is None:
        msg = '"%s" is not a valid OMOP table' % table_name
        print(msg)
        result['errors'].append(dict(message=msg))
        return result

    # get column names for this table
    cdm_column_names = [col['name'] for col in cdm_table_columns]

    if not os.path.isfile(file_path):
        print('File does not exist: %s' % file_path)
        return result

    try:
        print('Parsing CSV file for OMOP table "%s"' % table_name)

        format_errors = check_csv_format(f, cdm_column_names)
        for format_error in format_errors:
            result['errors'].append(
                dict(message=format_error[0],
                     actual=format_error[1],
                     expected=format_error[2]))

        csv_columns = list(pd.read_csv(f, nrows=1).columns.values)
        datetime_columns = [
            col_name.lower() for col_name in csv_columns
            if 'date' in col_name.lower()
        ]
        f.seek(0)

        blank_lines = find_blank_lines(f)
        if blank_lines:
            blank_lines_str = ",".join(map(str, blank_lines))
            line_str = 'lines' if len(blank_lines) > 1 else 'line'
            blank_lines_msg = f'File contains blank {line_str} on {line_str} {blank_lines_str}. ' \
                              'If there is no data, please only submit the header line.'

            result['errors'].append(dict(message=blank_lines_msg))
            return result

        f.seek(0)

        # check columns if looks good process file
        if not _check_columns(cdm_column_names, csv_columns, result):
            return result

        #search for scientific notation
        int_columns = [
            col['name'] for col in cdm_table_columns
            if col['type'] == 'integer'
        ]
        sci_not_errors = find_scientific_notation_errors(f, int_columns)
        for sci_not_error in sci_not_errors:
            result['errors'].append(sci_not_error)

        f.seek(0)

        # read file to be processed
        df = pd.read_csv(f,
                         sep=',',
                         na_values=['', ' ', '.'],
                         parse_dates=False,
                         infer_datetime_format=False)


        # Check each column exists with correct type and required
        for meta_item in cdm_table_columns:
            meta_column_name = meta_item['name']
            meta_column_required = meta_item['mode'] == 'required'
            meta_column_type = meta_item['type']
            submission_has_column = False

            for submission_column in df.columns:
                if submission_column == meta_column_name:
                    submission_has_column = True
                    submission_column_type = df[submission_column].dtype

                    # If all empty don't do type check
                    if not df[submission_column].isnull().values.all():
                        if not type_eq(meta_column_type,
                                       submission_column_type):
                            # find the row that has the issue
                            error_row_index = find_error_in_file(
                                submission_column, meta_column_type,
                                submission_column_type, df)
                            if error_row_index:
                                if not (pd.isnull(
                                        df[submission_column][error_row_index])
                                        and not meta_column_required):
                                    e = dict(message=MSG_INVALID_TYPE +
                                             " line number " +
                                             str(error_row_index + 1),
                                             column_name=submission_column,
                                             actual=df[submission_column]
                                             [error_row_index],
                                             expected=meta_column_type)
                                    result['errors'].append(e)

                        # Check that date format is in the YYYY-MM-DD or YYYY-MM-DD hh:mm:ss format
                        if meta_column_type in ('date', 'timestamp'):
                            fmt = ''
                            err_msg = ''

                            if meta_column_type == 'date':
                                fmts = VALID_DATE_FORMAT
                                err_msg = MSG_INVALID_DATE
                            elif meta_column_type == 'timestamp':
                                fmts = VALID_TIMESTAMP_FORMAT
                                err_msg = MSG_INVALID_TIMESTAMP

                            for idx, value in df[submission_column].iteritems(
                            ):
                                if not any(
                                        list(
                                            map(
                                                lambda fmt:
                                                date_format_valid(
                                                    str(value), fmt),
                                                fmts))):
                                    if not (pd.isnull(value)
                                            and not meta_column_required):
                                        e = dict(message=err_msg +
                                                 ": line number " +
                                                 str(idx + 1),
                                                 column_name=submission_column,
                                                 actual=value,
                                                 expected=meta_column_type)
                                        result['errors'].append(e)
                                        #only return the first error
                                        break

                    # Check if any nulls present in a required field
                    if meta_column_required and df[submission_column].isnull(
                    ).sum() > 0:
                        # submission_column['stats']['nulls']:
                        result['errors'].append(
                            dict(message=MSG_NULL_DISALLOWED,
                                 column_name=submission_column))
                    continue

            # Check if the column is required
            if not submission_has_column and meta_column_required:
                result['errors'].append(
                    dict(message='Missing required column',
                         column_name=meta_column_name))
    except Exception as e:
        print(traceback.format_exc())
        # Adding error message if there is a wrong number of columns in a row
        result['errors'].append(dict(message=e.args[0].rstrip()))
    else:
        print(
            'CSV file for "%s" parsed successfully. Please check for errors in the results files.'
            % table_name)
    return result


def process_file(file_path):
    """
    This function processes the submitted file
    :return: A dictionary of errors found in the file. If there are no errors,
    then only the error report headers will in the results.
    """

    enc = detect_bom_encoding(file_path)
    if enc is None:
        with open(file_path, 'r') as f:
            result = run_checks(file_path, f)
    else:
        with open(file_path, 'r', encoding=enc) as f:
            result = run_checks(file_path, f)
    print('Finished processing %s\n' % file_path)
    return result


def _check_columns(cdm_column_names, csv_columns, result):
    """
    This function checks if the columns in the submission matches those in CDM definition
    :return: A dictionary of errors of mismatched columns
    """
    columns_valid = True

    # if len(csv_columns) != len(cdm_column_names):

    # check all column headers in the file
    for col in csv_columns:
        if col not in cdm_column_names:
            e = dict(message=MSG_INCORRECT_HEADER, column_name=col, actual=col)
            result['errors'].append(e)
            columns_valid = False

    # check cdm table headers against headers in file
    for col in cdm_column_names:
        if col not in csv_columns:
            e = dict(message=MSG_MISSING_HEADER, column_name=col, expected=col)
            result['errors'].append(e)
            columns_valid = False

    # check order of cdm table headers against headers in file
    for idx, col in enumerate(cdm_column_names):
        if idx < len(csv_columns) and csv_columns[idx] != col:
            e = dict(message=MSG_INCORRECT_ORDER,
                     column_name=csv_columns[idx],
                     actual=csv_columns[idx],
                     expected=col)
            result['errors'].append(e)
            columns_valid = False
            break

    return columns_valid


def generate_pretty_html(html_output_file_name):
    lines = []
    with open(settings.html_boilerplate, 'r') as f:
        lines.extend(f.readlines())
    lines.append('<table id="dataframe" style="width:80%" class="center">\n')
    with open(html_output_file_name, 'r') as f:
        lines.extend(f.readlines()[1:])
    lines.extend(['\n', '</body>\n', '</html>\n'])
    with open(html_output_file_name, 'w') as f:
        for line in lines:
            f.write(line)


def evaluate_submission(d):
    out_dir = os.path.join(d, 'errors')
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    output_file_name = os.path.join(out_dir, 'results.csv')
    error_map = {}

    readable_field_names = [
        get_readable_key(field_name) for field_name in HEADER_KEYS + ERROR_KEYS
    ]
    df = pd.DataFrame(columns=readable_field_names)
    table_names = collections.defaultdict()

    for key in HEADER_KEYS + ERROR_KEYS:
        new_key = get_readable_key(key)
        table_names[key] = new_key

    for f in glob.glob(os.path.join(d, '*.csv')):
        file_path_parts = f.split(os.sep)
        file_name = file_path_parts[-1]

        result = process_file(f)
        rows = []
        for error in result['errors']:
            row = []
            for header_key in HEADER_KEYS:
                row.append(result.get(header_key))
            for error_key in ERROR_KEYS:
                row.append(error.get(error_key))
            rows.append(row)

        if len(rows) > 0:
            df_file = pd.DataFrame(rows, columns=readable_field_names)
            df = df.append(df_file, ignore_index=True)

        error_map[file_name] = result['errors']
    df.to_csv(output_file_name, index=False, quoting=csv.QUOTE_ALL)

    # changing extension
    html_output_file_name = output_file_name[:-4] + '.html'

    df = df.fillna('')
    df.to_html(html_output_file_name, index=False)
    generate_pretty_html(html_output_file_name)

    return error_map


if __name__ == '__main__':
    evaluate_submission(settings.csv_dir)
