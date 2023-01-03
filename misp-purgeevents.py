#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Created by Dennis Rand
# eCrimeLabs ApS
# https://www.ecrimelabs.com
#

import argparse
import re
import json
import sys
import arrow
import pprint
import datetime
import time
import signal
import requests
import uuid
from tendo import singleton
from pymisp import ExpandedPyMISP
from pymisp import PyMISP
from collections import defaultdict
from config import misp_url, misp_key, misp_verifycert, exclude_orgs, chunk_size

verbose = False
dryrun = False
blocklisted = False
version = '0.1'

def handler(signum, frame):
    print ("")
    res = input("Ctrl-c was pressed. Do you really want to exit? y/n ")
    if res == 'y':
        sys.exit(1)

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def timestamp_today():
    return(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"))

def timestamp_yesterday():
    today = datetime.datetime.utcnow().date()
    yesterday = today - datetime.timedelta(days=1)
    return(str(yesterday))

def timestamp():
    return(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z - "))

def valid_date(date_string):
    try:
        datetime.datetime.strptime(date_string, '%Y-%m-%d')
        return(True)
    except ValueError:
        return(False)

def get_active_lists_fixed_id(misp):
    '''
        Search for fixed event ID's added to Feeds.
        Returns: List of MISP ID's
    '''
    global verbose
    exclude_event_ids = []
    response_lists = misp.feeds()
    for list in response_lists:
        if (int(list['Feed']['event_id']) > 0):
            exclude_event_ids.append(list['Feed']['event_id'])
    if (verbose):
        print (" - " + str(len(exclude_event_ids)) + " fixed events for exclusion from Feeds")
    return(exclude_event_ids)

def search_and_delete_blocklist_events(misp, earliest, latest):
    global dryrun, verbose, exclude_orgs
    cntSuccess = 0
    cntFailed = 0
    print (" - Searching and deleting blocklisted events in MISP based event date (NOTICE: This can take some time)")
    try:
        response_lists = misp.event_blocklists()
    except:
        print (" - An Error occoured in search for events")
        sys.exit(1)
    if (verbose):
        print (" - Deleting Blocklisted Events:")
    formatted_earliest_date = time.strptime(earliest + ' 00:00:01', "%Y-%m-%d %H:%M:%S")
    formatted_latest_date = time.strptime(latest + ' 23:59:59', "%Y-%m-%d %H:%M:%S")
    for response in response_lists:
            created_at = response['created']
            event_uuid = response['event_uuid']
            formatted_created_date = time.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            if ((formatted_created_date >= formatted_earliest_date) and (formatted_created_date <= formatted_latest_date)):
                if (verbose):
                    if (dryrun):
                        print ("   + Blocklisted Event UUID: " + event_uuid)
                    else:
                        print ("   + Blocklisted Event UUID: " + event_uuid, end =" -> ")
                if not (dryrun):
                    result = misp.delete_event_blocklist(event_uuid)
                    if (verbose):
                        if (result['success']):
                            print ("OK")
                            cntSuccess = cntSuccess + 1
                        else:
                            print ("FAILED")
                            cntFailed = cntFailed + 1
                else:
                    cntSuccess = cntSuccess + 1
    return(cntSuccess,cntFailed)




def search_misp_events(misp, time_list, exclude_event_ids, orguuid):
    global dryrun, verbose, exclude_orgs
    print ("  - Searching events in MISP between " + time_list[0] + " and " + time_list[1])
    search_template = {
        "published": "1",
        "minimal": "1",
    }
    search_template['datefrom'] = time_list[0]
    search_template['dateuntil'] = time_list[1]

    events = []
    org_counter = 0
    try:
        response_lists = misp.direct_call('/events/index', search_template)
    except:
        print (" - An Error occoured in search for events")
        sys.exit(1)
    for response in response_lists:
        event_uuid = response['uuid']
        orgc_uuid = response['orgc_uuid']
        event_id = response['id']
        if not orgc_uuid in exclude_orgs:
            if not event_id in exclude_event_ids:
                if(is_valid_uuid(orguuid)):
                    if (orgc_uuid == orguuid):
                        events.append(int(event_id))
                else:
                    events.append(int(event_id))
        else:
            org_counter = org_counter + 1
    if (verbose or dryrun):
        if(is_valid_uuid(orguuid)):
            print ("  - 0 events excluded based on OrgC UUID's")
        else:
            print ("  - " + str(org_counter) + " events excluded based on OrgC UUID's")
        if (verbose):
            print ("  - Excluded OrgC UUID(s):")
            for exclude_org in exclude_orgs:
                print ("   + OrgC UUID: " + exclude_org)
    return(events)

def delete_misp_events(misp, event_db):
    global dryrun, verbose, misp_url, misp_key, chunk_size
    cntSuccess = 0
    cntFailed = 0
    bulk = {}
    if (len(event_db) > 0):
        bulk['id'] = event_db
        app_json = json.dumps(bulk)
        url = misp_url + '/events/delete'
        try:
            x = requests.post(url, data=app_json, headers={"Content-Type":"application/json", "Accept":"application/json", "Authorization": misp_key }, timeout=60, verify=misp_verifycert)
            cntSuccess = len(event_db)
        except:
            cntFailed = len(event_db)
    return(cntSuccess,cntFailed)

def perform_task(first, last, blocklisted, force, orguuid):
    global dryrun, verbose, split_freq, chunk_size
    cntSuccessSum = 0
    cntFailedSum = 0
    me = singleton.SingleInstance() # will sys.exit(-1) if other instance is running
    delete_data = False
    if (force == False and dryrun == False):
        answer = input(" - Continue data deletion in MISP (answer: YES to continue)?")
        if answer.upper() in ["Y", "YES"]:
            delete_data = True
        else:
            delete_data = False
            print (" - Data purge has exited use '--dryrun' for test or '--force' to run automated")
            sys.exit(0)
    else:
        delete_data = True

    if (delete_data):
        signal.signal(signal.SIGINT, handler)
        misp = ExpandedPyMISP(misp_url, misp_key, misp_verifycert)
        exclude_event_ids = get_active_lists_fixed_id(misp)

        formatted_earliest_date = time.strptime(first, "%Y-%m-%d")
        formatted_latest_date = time.strptime(last, "%Y-%m-%d")
        if (formatted_latest_date < formatted_earliest_date):
            print (" - Failed since first seen (" + first + ") is after last seen (" + last + ")")
            sys.exit(1)
        if (blocklisted):
            cntSuccess,cntFailed = search_and_delete_blocklist_events(misp, first, last)
            print (" - Result: " + str(cntSuccess) + " blocklisted events deleted, and " + str(cntFailed) + " Failed")
        else:
            time_list = [str(first), str(last)]
            event_db = search_misp_events(misp, time_list, exclude_event_ids, orguuid)
            if (len(event_db) < chunk_size):
                print("  - " + str(len(event_db)) + " events identified and up for deletion")
            else:
                print("  - " + str(len(event_db)) + " events identified and up for deletion, splitting into chunks of " + str(chunk_size))
            if (dryrun):
                    print ("------------------------------------------")
                    print ("- Simulated Purge Completed")
                    sys.exit(0)
            if (len(event_db) > 0):
                chunked_list = list()
                loop_sleep = 0
                for i in range(0, len(event_db), chunk_size):
                    chunked_list.append(event_db[i:i+chunk_size])

                for event_db in chunked_list:
                    failed_attempts = 0
                    cntSuccess, cntFailed = delete_misp_events(misp, event_db)
                    cntSuccessSum = cntSuccessSum + cntSuccess
                    cntFailedSum = cntFailedSum + cntFailed
                    if(verbose):
                        print ("    - Result: " + str(cntSuccess) + " event(s) deleted, and " + str(cntFailed) + " Failed")
                    loop_sleep = loop_sleep + 1
                    if (cntFailed >= 1):
                        loop_sleep = 0
                        failed_attempts = failed_attempts + 1
                        if (force == False):
                            print ("    - Sleeping 360 seconds - To give database time to recover and cleanup - Failed attempts")
                            time.sleep(360)
                    elif (loop_sleep == 10):
                        loop_sleep = 0
                        if (force == False):
                            print ("    - Sleeping 120 seconds - To give database time to recover and cleanup - when another chunk of <={} events will be deleted".format(chunk_size*10))
                            time.sleep(120)
                    elif (failed_attempts > 3):
                        print ("- Multiple failed concurrent attempts... Exiting")
                        sys.exit(1)
                    else:
                        failed_attempts = 0
                        pass
        print ("  - Summarized Result: " + str(cntSuccessSum) + " events deleted, and " + str(cntFailedSum) + " Failed")
        print (" ------------------------------------------")

def main():
    global dryrun, verbose, blocklisted

    print ("eCrimeLabs MISP Purge Events tool v." + str(version))
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--first", type=str, default=timestamp_yesterday(), help="Oldest events to purge - Format: YYYY-MM-DD (Default: " + timestamp_yesterday() + ")")
    parser.add_argument("-l", "--last", type=str, default=timestamp_today(), help="Newest events to purge - Format: YYYY-MM-DD (Default: " + timestamp_today() + ")")
    parser.add_argument("-d", "--dryrun", default=False, action='store_true', help="Dryrun will not perform the deletion but output how many entries would be deleted.")
    parser.add_argument("-v", "--verbose", default=False, action='store_true', help="Will output a list of the event UUID deleted, while running")
    parser.add_argument("-b", "--blocklist", default=False, action='store_true', help="The purge will be done towards events listed in the BlockListed Events")
    parser.add_argument("-o", "--orguuid", type=str, help="Specify a specific organization UUID to perform purge on - Format: 123e4567-e89b-12d3-a456-426614174000")
    parser.add_argument("--force", default=False, action='store_true', help="The purge will performed, without asking for confirmation [WARNING - DELETION WILL BE DONE]")

    args = parser.parse_args()
    verbose = args.verbose
    dryrun = args.dryrun
    blocklisted = args.blocklist
    force = args.force
    orguuid = ""

    if not (valid_date(args.first)):
        print(" - First seen date seen date (" + args.first + ") has incorrect date string format. It should be YYYY-MM-DD")
        sys.exit(1)
    elif not (valid_date(args.last)):
        print(" - Last seen date seen date (" + args.last + ") has incorrect date string format. It should be YYYY-MM-DD")
        sys.exit(1)

    if (dryrun):
        print (" - Running in dryrun mode (NO DATA WILL BE DELETED)")
    if (blocklisted):
        print(" - Find Blocklisted events for deletion between: " + args.first + " and " + args.last)
    else:
        if args.orguuid is not None:
            if (is_valid_uuid(args.orguuid)):
                orguuid = args.orguuid
                print(" - Find events from organization " + orguuid + " for deletion between: " + args.first + " and " + args.last)
            else:
                print ("ERROR: Invalid UUID(" + str(args.orguuid) + ") format, exiting")
                sys.exit(1)
        else:
            print(" - Find all events for deletion between: " + args.first + " and " + args.last)

    perform_task(args.first, args.last, blocklisted, force, orguuid)
    if (dryrun):
        print (" - Simulated Purge Completed")
    else:
        print (" - Purge Completed")

if __name__ == '__main__':
    main()
