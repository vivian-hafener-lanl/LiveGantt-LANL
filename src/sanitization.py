import pandas as pd
import datetime
from procset import ProcSet


def twenty22():
    """
    Defines a series of variables linked to the column names of the format being used
    :return:
    """
    global endState, wallclockLimit, reqNodes, submit, start, end, jobId, reservation
    endState = "State"
    wallclockLimit = "Timelimit"
    reqNodes = "NNodes"
    submit = "Submit"
    start = "Start"
    end = "End"
    jobId = "JobID"
    reservation = "Reservation"

    # Define a function to strip leading zeroes from each individual value


def strip_leading_zeroes(s):
    """
    Strip the leading zeroes from each resource value. Used in the allocated_resources column.
    :param s: The string from which to strip leading zeros.
    :return: The string with the values stipped from it.
    """
    values = s.split()
    stripped_values = []
    for value in values:
        parts = value.split('-')
        stripped_parts = [part.lstrip('0') for part in parts]
        stripped_value = '-'.join(stripped_parts)
        stripped_values.append(stripped_value)
    return ' '.join(stripped_values)


# Define a function to convert the string to a ProcSet
def string_to_procset(s):
    """
    Return a ProcSet parsed from a string
    :param s: String to convert
    :return: The resulting ProcSet
    """
    return ProcSet.from_str(s)


def sanitizeFile(inputfile):
    """
    Sanitize the data provided from sacct.out in order to ensure that jobs that didn't exist or didn't fit expected bounds don't interfere with chart production.
    :param inputfile: The file to convert to CSV and sanitize job data from
    :return: The sanitized dataframe
    """

    # Using 2022 fog data
    twenty22()

    df = pd.read_csv(inputfile)
    df.head()

    # TODO I don't want to overfilter this. I can eventually see which ones of these actually make sense for live data as opposed to sim data.

    # Jobs that have not ended yet, make them end now. This means that the chart will show jobs that are currently running, in addition to jobs that have finished.
    df[end] = df[end].replace('Unknown', datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))

    # Remove jobs that were cancelled
    df[endState] = df[endState].replace('^CANCELLED by \d+', 'CANCELLED', regex=True)
    # Remove jobs that have duplicate job IDs
    # sanitizing_df = df.drop_duplicates(subset=[jobId], keep="last") # TODO Unstub?
    sanitizing_df = df  # TODO Unstub
    # Remove jobs that requested 0 nodes
    sanitizing_df = sanitizing_df.loc[sanitizing_df[reqNodes] != 0]
    # Remove jobs that have a wallclocklimit of 0
    sanitizing_df = sanitizing_df.loc[sanitizing_df[wallclockLimit] != 0]
    # Remove jobs with the same start & end timestamps
    sanitizing_df = sanitizing_df.loc[sanitizing_df[end] != sanitizing_df[start]]
    # Remove jobs with an unknown end state
    sanitizing_df = sanitizing_df.loc[sanitizing_df[end] != "Unknown"]
    # Remove jobs with an unknown start state
    sanitizing_df = sanitizing_df.loc[sanitizing_df[start] != "Unknown"]
    # Remove jobs with an unknown submit state
    sanitizing_df = sanitizing_df.loc[sanitizing_df[submit] != "Unknown"]
    # Remove jobs that have a null start
    sanitizing_df = sanitizing_df.loc[~sanitizing_df[start].isna()]
    # Remove jobs that have an end that is not after the start
    sanitizing_df = sanitizing_df.loc[sanitizing_df[end] > sanitizing_df[start]]
    # Set the reservation field properly
    # TODO I can specify!!! For now it'll just be DAT,DST, and PreventMaint but in the future I can show it different for each!

    # Define the replacement rules using regular expressions
    replacement_rules = {
        'DST': 'reservation',
        'DAT.*': 'reservation',
        'PreventMaint$': 'reservation',
        None: 'job',
        '': 'job',
    }

    # Replace values in the "reservation" column based on the rules
    sanitizing_df[reservation] = sanitizing_df[reservation].replace(replacement_rules, regex=True)
    sanitizing_df.loc[~sanitizing_df[reservation].isin(['reservation', 'job']), reservation] = 'job'

    # Rename the columns in the incoming DF to the target names
    formatted_df = sanitizing_df.rename(columns={
        'JobIDRaw': 'jobID',
        'Submit': 'submission_time',
        'NNodes': 'requested_number_of_resources',
        'State': 'success',
        'Start': 'starting_time',
        'End': 'finish_time',
        'NodeList': 'allocated_resources',
        'Reservation': 'purpose'
    })

    # Convert times into the preferred time format
    columns_to_convert = ['submission_time', 'starting_time', 'finish_time']
    # Loop through the specified columns and convert values to datetime objects
    for col in columns_to_convert:  # TODO I could do __converters instead on pd.read_csv
        formatted_df[col] = formatted_df[col].apply(lambda x: datetime.datetime.strptime(x, '%Y-%m-%dT%H:%M:%S'))

    # Strip node titles from the allocated_resources space. This will need to be updated for every cluster it is run
    # on. Then replace the pipe separator used in the allocated resources field with a space, which is preferred for
    # parsing here-on-in
    formatted_df['allocated_resources'] = formatted_df['allocated_resources'].apply(
        lambda x: x.strip("fg[]sn").replace("|", " "))

    # Apply the strip_leading_zeros function to the 'allocated resources' column
    formatted_df['allocated_resources'] = formatted_df['allocated_resources'].apply(strip_leading_zeroes)
    # Apply the string_to_procset function to the allocated_resources column
    formatted_df['allocated_resources'] = formatted_df['allocated_resources'].apply(string_to_procset)
    # Set default values for some columns
    formatted_df['workload_name'] = 'w0'
    formatted_df['execution_time'] = formatted_df['finish_time'] - formatted_df['starting_time']
    formatted_df['waiting_time'] = formatted_df['starting_time'] - formatted_df['submission_time']
    formatted_df['requested_time'] = formatted_df['execution_time']
    formatted_df['turnaround_time'] = formatted_df['finish_time'] - formatted_df['submission_time']
    formatted_df['stretch'] = formatted_df['turnaround_time'] / formatted_df['requested_time']

    # Reorder the columns to match the specified order
    formatted_df = formatted_df[[
        'jobID',
        'workload_name',
        'submission_time',
        'requested_number_of_resources',
        'requested_time',
        'success',
        'starting_time',
        'execution_time',
        'finish_time',
        'waiting_time',
        'turnaround_time',
        'stretch',
        'allocated_resources',
        'purpose',
    ]]

    return formatted_df
