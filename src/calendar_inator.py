from __future__ import print_function
import pickle
import os.path
import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from guizero import App, Box, Text
from pprint import pprint
import sqlite3

conn = sqlite3.connect(':memory:')
c = conn.cursor()
# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def main():
    global c, conn, SCOPES
    global app

    c.execute('CREATE TABLE calendar (id INTEGER PRIMARY KEY, start TEXT, end TEXT, event TEXT)')
    
    startGui()
    startGoogleService()
    ourCalendars = getCalendars()
    putEventsInDB(ourCalendars)
    populateCalendar()

    app.repeat((60*60*1000),populateCalendar) # every hour   
    app.display()
    


    
def startGoogleService():
    global service
    # This is straight out of the Google sample project to get things connected
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)
     
    
    
def getCalendars(): 
    global service    
    calendars_result = service.calendarList().list().execute()

    calendars = calendars_result.get('items', [])
   
    ourCalendars = []
    for calendar in calendars:
            ourCalendars.append(calendar['id'])
    return ourCalendars

def putEventsInDB(ourCalendars):
    global c, conn, service
    # Call the Calendar API
    now = datetime.datetime.utcnow()
    now = now + datetime.timedelta(days=-1)
    now = now.isoformat() + 'Z' # 'Z' indicates UTC time

    
    for id in ourCalendars:
        events_result = service.events().list(calendarId=id, timeMin=now,
                                            maxResults=30, singleEvents=True,
                                            orderBy='startTime').execute()
        events = events_result.get('items', [])


        for event in events:
            c.execute("INSERT INTO calendar (start, end, event) VALUES (?,?,?)",
                (event['start'].get('dateTime', event['start'].get('date')),
                event['end'].get('dateTime', event['end'].get('date')),
                event['summary']))
            conn.commit()


def startGui():
    global app
    global headerText, eventText
    app = App(title = "Calendar-inator", layout = "grid", width = 1050, height = 150)
    dayBox = []
    headerText = []
    eventText = []
    for x in range(0,7):
        dayBox.append(Box(app, grid=[x, 0], border=True, width=150, height=150))
        headerText.append(Text(dayBox[x], size=12))
        eventText.append(Text(dayBox[x], size=10))
        
def populateCalendar():
    now = datetime.datetime.now()
    print(now.strftime("%Y-%m-%d %H:%M:%S")+" populateCalendar")
    now = datetime.date.today()
    global headerText, eventText, c
    displayText = ["","","","","","",""]
    for x in range(0,7):
        dow = now + datetime.timedelta(days=x)
        nowDB = dow.strftime("%Y-%m-%d")
        tonightDB = dow.strftime("%Y-%m-%dT23:59:59")
        headerText[x].value = dow.strftime("%A")
        sqlQuery = "SELECT DISTINCT start, end, event FROM calendar WHERE start BETWEEN '"+nowDB
        sqlQuery += "' and '"+tonightDB+"' ORDER BY start;"
        for row in c.execute(sqlQuery):
            displayText[x] = displayText[x]+row[2]+"\n"
    for x in range(0,7):
        eventText[x].value = displayText[x]



if __name__ == '__main__':
    main()