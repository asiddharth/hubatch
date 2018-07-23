"""
Parses content from CSV files
"""
import csv, os

OUTPUT_DIR = "./output/"

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

def write_items_to_csv(item_list, file_list, week, level) :
    """
    Writes a list of items into files
    :param item_list:
    :param file_list:
    :return:
    """
    output_path = OUTPUT_DIR+"/AB{}/week_{}/".format(level, week)

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    for item, filename in zip(item_list, file_list) :
        wr = csv.writer(open(output_path+filename+".csv", 'w'), delimiter=',', 
                            quoting=csv.QUOTE_ALL)
        for row in item:
            wr.writerow(row)