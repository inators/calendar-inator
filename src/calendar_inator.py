#!/usr/bin/python3
import pickle
import os.path
import datetime
from time import gmtime, strftime, time, sleep
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from guizero import App, Box, Text
from pprint import pprint
import sqlite3
import textwrap
import socket
import requests
import logging
import sys
import os
from colors import Colors

filename = os.path.basename(__file__)
home = os.path.expanduser("~")
logger = logging.getLogger(f"{Colors.RED}{filename}{Colors.END}")
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s',
                     filename=home + "/mylogs.log")
logger.info("Program start.")
sys.stderr.write = logger.error
sys.stdout.write = logger.info
logging.getLogger('googleapicliet.discovery_cache').setLevel(logging.ERROR)

conn = sqlite3.connect(":memory:")
c = conn.cursor()
# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def main():
    global c, conn, SCOPES
    global app

    c.execute(
        "CREATE TABLE calendar (id INTEGER PRIMARY KEY, start TEXT, end TEXT, event TEXT)"
    )

    startGui()
    startGoogleService()
    ourCalendars = getCalendars()
    putEventsInDB(ourCalendars)
    populateCalendar()

    app.repeat((60 * 60 * 1000), refreshCalendar)  # every hour
    app.display()


def refreshCalendar():
    global c
    try:
        ourCalendars = getCalendars()
    except:  # not a big deal if we don't update this round.  Will try again in an hour.
        print("Calendar failure")
        return
    c.execute("DELETE FROM calendar")  # clear the memory so we start fresh
    putEventsInDB(ourCalendars)
    populateCalendar()


def startGoogleService():
    global service
    # This is straight out of the Google sample project to get things connected
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(f"{home}/calendarinatorCreds.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    service = build("calendar", "v3", credentials=creds)


def getCalendars():
    global service
    calendars_result = service.calendarList().list().execute()

    calendars = calendars_result.get("items", [])

    ourCalendars = []
    for calendar in calendars:
        ourCalendars.append(calendar["id"])
    return ourCalendars


def putEventsInDB(ourCalendars):
    global c, conn, service

    now = datetime.datetime.utcnow()
    now = now + datetime.timedelta(days=-1)
    now = now.isoformat() + "Z"  # 'Z' indicates UTC time

    for id in ourCalendars:
        events_result = (
            service.events()
            .list(
                calendarId=id,
                timeMin=now,
                maxResults=30,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        for event in events:

            if "dateTime" in event["start"]:
                thisString = event["start"]["dateTime"]
                if thisString.find("Z") > 0:
                    tempDateTime = datetime.datetime.strptime(
                        thisString, "%Y-%m-%dT%H:%M:%SZ"
                    )
                    # Convert it to our time zone
                    timeStamp = datetime.datetime.timestamp(tempDateTime)
                    now_timestamp = time()
                    offset = datetime.datetime.fromtimestamp(
                        now_timestamp
                    ) - datetime.datetime.utcfromtimestamp(now_timestamp)
                    tempDateTime = datetime.datetime.fromtimestamp(timeStamp)
                    tempDateTime = tempDateTime + offset
                    event["start"]["dateTime"] = datetime.datetime.strftime(
                        tempDateTime, "%Y-%m-%dT%H:%M:%S"
                    )

            try:
                c.execute(
                    "INSERT INTO calendar (start, end, event) VALUES (?,?,?)",
                    (
                        event["start"].get("dateTime", event["start"].get("date")),
                        event["end"].get("dateTime", event["end"].get("date")),
                        event["summary"],
                    ),
                )
                conn.commit()
            except:
                pprint(event)


def startGui():
    global app
    global headerText, eventText
    app = App(title="Calendar-inator", layout="grid", width=1400, height=200)
    app.tk.geometry('%dx%d+%d+%d' % (1400, 200, 0, 850))
    
    dayBox = []
    headerText = []
    eventText = []
    for x in range(0, 7):
        dayBox.append(Box(app, grid=[x, 0], border=True, width=200, height=200))
        headerText.append(Text(dayBox[x], size=16))
        eventText.append(Text(dayBox[x], size=12))


def populateCalendar():
    now = datetime.datetime.now()
    print(now.strftime("%Y-%m-%d %H:%M:%S") + " populateCalendar")
    now = datetime.date.today()
    global headerText, eventText, c
    displayText = ["", "", "", "", "", "", ""]
    for x in range(0, 7):
        dow = now + datetime.timedelta(days=x)
        nowDB = dow.strftime("%Y-%m-%d")
        tonightDB = dow.strftime("%Y-%m-%dT23:59:59")
        headerText[x].value = dow.strftime("%A")
        sqlQuery = (
            "SELECT DISTINCT start, end, event FROM calendar WHERE start BETWEEN '"
            + nowDB
        )
        sqlQuery += "' and '" + tonightDB + "' ORDER BY start;"
        for row in c.execute(sqlQuery):
            if row[0].find("T") > 0:
                thisString = row[0]

                if thisString.count("-") == 3:
                    thisString = thisString[0:-6]

                tempDateTime = datetime.datetime.strptime(
                    thisString, "%Y-%m-%dT%H:%M:%S"
                )
                timeOutput = datetime.datetime.strftime(
                    tempDateTime, " %I:%M%p "
                ).replace(" 0", " ")
            else:
                timeOutput = ""
            printString = row[2]
            if len(printString) > 16:
                lines = textwrap.wrap(printString, 16)
                printString = "\n".join(lines)
            displayText[x] = displayText[x] + timeOutput + printString + "\n"
    for x in range(0, 7):
        eventText[x].value = displayText[x]
    app.update()

def has_internet():
    try:
        requests.get("https://www.google.com", timeout=5)
        logging.info("internet connection obtained!")
        return True
    except requests.ConnectionError:
        logging.info("No internet connection yet.")
        return False


if __name__ == "__main__":
    try:
        while not has_internet():
            print("Waiting for internet...")
            time.sleep(5)
        main()
    except Exception as e:
        logging.exception("Something happened")
