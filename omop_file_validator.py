import glob
import traceback

import settings
import os
import codecs
import pandas as pd
import csv
import json
import datetime
import collections

RESULT_SUCCESS = 'success'
MSG_CANNOT_PARSE_FILENAME = 'Cannot parse filename'
MSG_INVALID_TYPE = 'Type mismatch'
MSG_INCORRECT_HEADER = 'Column not in table definition'
MSG_MISSING_HEADER = 'Column missing in file'
MSG_INCORRECT_ORDER = 'Column not in expected order'
MSG_NULL_DISALLOWED = 'NULL values are not allowed for column'

HEADER_KEYS = ['file_name', 'table_name']
ERROR_KEYS = ['message', 'column_name', 'actual', 'expected']


def get_readable_key(key):
    new_key = key.replace('_', ' ')
    new_key = new_key.title()
    return new_key


def get_cdm_table_columns(table_name):
    # allow files to be found regardless of CaSe
    file=os.path.join(settings.cdm_metadata_path, table_name.lower() + '.json')
    if os.path.isfile(file):
        with open(file, 'r') as f:
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
    if cdm_column_type == 'numeric':
        return submission_column_type == 'float'
    raise Exception('Unsupported CDM column type ' + cdm_column_type)


def cast_type(cdm_column_type, value):
    """
    Compare column type in spec with column type in submission
    :param cdm_column_type:
    :param value:
    :return:
    """
    if cdm_column_type == 'integer':
        return int(value)
    if cdm_column_type in ('character varying', 'text', 'string'):
        return str(value)
    if cdm_column_type == 'numeric':
        return float(value)
    if cdm_column_type == 'date':
        return datetime.date(value)
    if cdm_column_type == 'timestamp':
        return datetime.datetime(value)


# code from: http://stackoverflow.com/questions/2456380/utf-8-html-and-css-files-with-bom-and-how-to-remove-the-bom-with-python
def get_bom_length(f):

    # read first 4 bytes
    header = f.read(4)

    # check for BOM
    bom_len = 0
    encodings = [(codecs.BOM_UTF32, 4),
                 (codecs.BOM_UTF16, 2),
                 (codecs.BOM_UTF8, 3)]

    # remove appropriate number of bytes
    for h, l in encodings:
        if header.startswith(h):
            bom_len = l
            break

    return bom_len


def remove_bom(f):
    bom_len = get_bom_length(f)
    f.seek(0)
    f.read(bom_len)
    return f


#finds the first occurrence of an error for that column.
#currently, it does NOT find all errors in the column.
def find_error_in_file(column_name, cdm_column_type, submission_column_type, df):

    #for index, row in df.iterrows():
    for i, (index, row) in enumerate(df.iterrows()):

        try:
            if i <= len(df) - 1:
                #print(index)
                #print(row[column_name])
                if row[column_name]:
                    cast_type(cdm_column_type, row[column_name])
                else:
                    return False
            else:
                return False
        except ValueError:
            # print(row[column_name])
            return index


def process_file(file_path):
    """
    This function processes the submitted file
    :return: A dictionary of errors found in the file. If there are no errors,
    then only the error report headers will in the results.
    """

    file_name, file_extension = os.path.splitext(file_path)
    file_path_parts = file_name.split(os.sep)
    table_name = file_path_parts[-1]

    #get the column definitions for a particular OMOP table
    cdm_table_columns = get_cdm_table_columns(table_name)


    phase = 'Received CSV file "%s"' % table_name
    print(phase)

    result = {'passed': False, 'errors': []}
    result['file_name'] = table_name+file_extension
    print(table_name)
    result['table_name'] = get_readable_key(table_name)

    if cdm_table_columns is None:
        result['errors'].append(dict(message='File is not a OMOP CDM table: %s' % table_name))

    else:

        try:

            phase = 'Parsing CSV file %s' % file_path

            # get column names for this table
            cdm_column_names = [col['name'] for col in cdm_table_columns]

            if os.path.isfile(file_path):
                f = open(file_path, 'rb')
                csv_columns = list(pd.read_csv(remove_bom(f), nrows=1).columns.values)
                datetime_columns = [col_name.lower() for col_name in csv_columns if 'date' in col_name.lower()]

                #check columns if looks good process file
                if (_check_columns(cdm_column_names, csv_columns, result)):

                    # read file to be processed
                    df = pd.read_csv(remove_bom(f), na_values=['', ' ', '.'], parse_dates=datetime_columns,
                                     infer_datetime_format=True)
                    print(phase)

                    # lowercase field names
                    df = df.rename(columns=str.lower)

                    # Check each column exists with correct type and required
                    for meta_item in cdm_table_columns:
                        meta_column_name = meta_item['name']
                        meta_column_required = meta_item['mode']=='required'
                        meta_column_type = meta_item['type']
                        submission_has_column = False

                        for submission_column in df.columns:
                            if submission_column == meta_column_name:
                                submission_has_column = True
                                submission_column_type = df[submission_column].dtype

                                # If all empty don't do type check
                                if submission_column_type != None:
                                    if not type_eq(meta_column_type, submission_column_type):

                                        #find the row that has the issue
                                        error_row_index = find_error_in_file(submission_column, meta_column_type, submission_column_type, df)
                                        if error_row_index :
                                            e = dict(message=MSG_INVALID_TYPE+" line number "+str(error_row_index+1),
                                                 column_name=submission_column,
                                                 actual=df[submission_column][error_row_index],
                                                 expected=meta_column_type)
                                            result['errors'].append(e)

                                # Check if any nulls present in a required field
                                if meta_column_required and df[submission_column].isnull().sum()>0:#submission_column['stats']['nulls']:
                                    result['errors'].append(dict(message=MSG_NULL_DISALLOWED,
                                                                 column_name=submission_column))
                                continue

                        #Check if the column is required
                        if not submission_has_column and meta_column_required:
                            result['errors'].append(dict(message='Missing required column', column_name=meta_column_name))
                f.close()

        except Exception as e:
            print(traceback.format_exc())
            #Adding error message if there is a wrong number of columns in a row
            result['errors'].append(dict(message=e.args[0].rstrip()))

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
            e = dict(message=MSG_INCORRECT_HEADER,
                     column_name=col,
                     actual=col)
            result['errors'].append(e)
            columns_valid = False

    # check cdm table headers against headers in file
    for col in cdm_column_names:
        if col not in csv_columns:
            e = dict(message=MSG_MISSING_HEADER,
                     column_name=col,
                     expected=col)
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

    readable_field_names = [get_readable_key(field_name) for field_name in HEADER_KEYS + ERROR_KEYS]
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
    html_output_file_name = output_file_name[:-4]+'.html'

    df = df.fillna('')
    df.to_html(html_output_file_name, index=False)
    generate_pretty_html(html_output_file_name)

    return error_map


if __name__ == '__main__':
    evaluate_submission(settings.csv_dir)
