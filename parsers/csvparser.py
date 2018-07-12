"""
Parses content from CSV files
"""
import csv

def get_rows_as_list(filename):
    """Returns a list of rows (represented as a list)"""
    with open(filename, newline='') as csvfile:
        csvreader = csv.reader(csvfile)
        return list(csvreader)

def get_rows_as_dict(filename):
    '''Returns as a dictionary of rows'''
    with open(filename, newline='') as csvfile:
        csvreader = csv.reader(csvfile)
        return {row[0]: row[1:] for row in csvreader}

def write_items_to_file(item_list, file_list) :
    """
    Writes a list of items into files
    :param item_list:
    :param file_list:
    :return:
    """
    for item, filename in zip(item_list, file_list) :
        with open(filename, 'w') as resfile:
            resfile.write('\n'.join(item))