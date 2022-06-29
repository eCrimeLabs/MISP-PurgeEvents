# eCrimeLabs MISP Purge Events tool

A python script to perform cleanup of old or unwanted events, including Blacklisted Events

Created by Dennis Rand [(@DennisRand)](https://twitter.com/dennisrand) - Company: eCrimeLabs ApS https://www.ecrimelabs.com

## Detailed Description
In various cases it would be useful to expire/purge older events, cleanup blocklist or delete events from a specific organization.

The MISP-PurgeOldEvent tool can assist in various cleaning operations

The tool supports exclusions on Organizations from purge, and also Feeds with fixed event will be excluded per default.  

**Notice:**
If a large set of events has to be purged it is highly recommended to disable/flush the correlation table prior, else we have seen MISP databases getting into unstable states, due to waits for cleanups in correlations.

This can be achieved by logging in to MISP as a site admin, and go through "Administration" -> "Server Settings & Administration" -> "MISP Settings" -> Change "MISP.completely_disable_correlation" to True

Validate that the correlations table has been clean by checking "Diagnostics" under "SQL database status".

When the large task is completed remember to enable correlations again.

**Warning:**
- It is always recommended to perform a backup prior to deletion of data, and as minimum do a dryrun first to understand the events to be deleted.
- Never run this on an MISP instance you do not own.

## Benchmarks
For a MISP instance with the below data volume (Correlations were removed prior to running the tool)
- Events: 9.460 (From 2011 and until 2022)
- Attributes: 1.424.251

Execution time **12m11.239s**

---

## Dependencies
It is recommended to create a virtual environment for the packages - **python 3.8 or higher** required.

Example for creating the virtual environment, can be executed from within the "MISP-PurgeOldEvents" folder
```
# python3 -m venv venv
```

**Installing the requirements:**
```
./venv/bin/pip install -r requirements.txt
```

---
## Config
Before you execute the tool the first time a few tasks has to be completed.

### config.py
rename the "config.py.template" to "config.py" and add in you MISP data and the organization UUID and chunk size and exclusion organizations

```
misp_url='https://<MISP DOMAIN>'
misp_key='<MISP KEY>'
misp_verifycert=True

# chunk_size is how many events to delete at a time.
chunk_size = 200

# Organization UUID's to exclude from deletion, typically you add your own organization.
exclude_orgs = [
     '1cb16c82-c808-4342-a874-60574c9c4df9',
     '569b6c1f-bd1c-49c8-9244-0484bce2ab96'
]
```

---

## Usage

**Help Menu:**
 ```
 $ venv/bin/python misp-purgeoldevents.py -h

 eCrimeLabs MISP Purge Old Events tool
 usage: misp-purgeoldevents.py [-h] [-f FIRST] [-l LAST] [-d] [-v] [-b] [-o ORGUUID] [--force]

 optional arguments:
   -h, --help            show this help message and exit
   -f FIRST, --first FIRST
                         Oldest events to purge - Format: YYYY-MM-DD (Default: 2022-06-26)
   -l LAST, --last LAST  Newest events to purge - Format: YYYY-MM-DD (Default: 2022-06-27)
   -d, --dryrun          Dryrun will not perform the deletion but output how many entries would be deleted.
   -v, --verbose         Will output a list of the event UUID deleted, while running
   -b, --blocklist       The purge will be done towards events listed in the BlockListed Events
   -o ORGUUID, --orguuid ORGUUID
                         Specify a specific organization UUID to perform purge on - Format: 123e4567-e89b-12d3-a456-426614174000
   --force               The purge will performed, without asking for confirmation [WARNING - DELETION WILL BE DONE]
 ```


### Examples

Delete all events between 2010-01-01 and 2022-12-12, excluding events created by Org UUID 569b6c1f-bd1c-49c8-9244-0484bce2ab96
 ```
 $ venv/bin/python misp-purgeoldevents.py -f 2010-01-01 -l 2022-12-12 -v --dryrun
 eCrimeLabs MISP Purge Old Events tool
  - Find all events for deletion between: 2010-01-01 and 2022-12-12
  - 1 fixed events for exclusion from Feeds
   - Searching events in MISP between 2010-01-01 and 2022-12-12
   - 15 events exluded based on OrgC UUID's
   - Excluded OrgC UUID(s):
    + OrgC UUID: 569b6c1f-bd1c-49c8-9244-0484bce2ab96
   - 9341 events identified and up for deletion, splitting into chunks of 200
 ```

Delete all events between 2010-01-01 and 2022-12-12, only events created by Organization UUID a40ea2c0-ff84-44ad-a936-7b1f5ab9725f
```
$ venv/bin/python misp-purgeoldevents.py -f 2010-01-01 -l 2022-12-12 -v -o a40ea2c0-ff84-44ad-a936-7b1f5ab9725f --dryrun
eCrimeLabs MISP Purge Old Events tool
 - Find events from organization a40ea2c0-ff84-44ad-a936-7b1f5ab9725f for deletion between: 2010-01-01 and 2022-12-12
 - 1 fixed events for exclusion from Feeds
  - Searching events in MISP between 2010-01-01 and 2022-12-12
  - 0 events exluded based on OrgC UUID's
  - Excluded OrgC UUID(s):
   + OrgC UUID: 1cb16c82-c808-4342-a874-60574c9c4df9
   + OrgC UUID: 569b6c1f-bd1c-49c8-9244-0484bce2ab96
  - 1 events identified and up for deletion
    - Result: 1 event(s) deleted, and 0 Failed
  - Summarized Result: 1 events deleted, and 0 Failed
 ------------------------------------------
 - Purge Completed
```

In some cases you need to do tests where you create events and delete these and looping that task, so you want to remove blocklisted events between 2010-01-01 and 2022-12-12
```
$ venv/bin/python misp-purgeoldevents.py -f 2010-01-01 -l 2022-12-12 --blocklist --dryrun
eCrimeLabs MISP Purge Old Events tool
 - Find Blocklisted events for deletion between: 2010-01-01 and 2022-12-12
 - 1 fixed events for exclusion from Feeds
 - Searching and deleting blocklisted events in MISP based event date (NOTICE: This can take some time)
 - Result: 4830 blocklisted events deleted, and 0 Failed
 - Summarized Result: 0 events deleted, and 0 Failed
------------------------------------------
- Purge Completed
```
