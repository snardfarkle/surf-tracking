# -*- coding: cp1252 -*-


#!/usr/bin/env python

# script to process a all fit files in a folder (assumes they are surf files)
# for each fit file
# read summary data and append to wave log file. log file is historical record of each wave. date/time/location/wave length/speed/distance
# converts raw garmin data (lat/long/time) to kml file
# does not check for duplicate fit files

# download garmin fit files from web using script

import fitparse                     # used to parse .fit files
from fitparse import FitFile
import time
import os
import re
from datetime import datetime, timedelta
from decimal import *               #used to format output of calculated values
import requests
from bs4 import BeautifulSoup
import urllib
import urllib2
import json
import googlemaps
import simplekml


api_key = '[enter your key here]'     #used for google maps api
api_key2 ='[enter your key here]'     #used for geocoding

# parameters for myFitFile.get_messages('xxxx')

# xxx =  'session'  #provides over arching data for file  i.e. sport:
# xxx =  'record'  #lat long data
# xxx = 'lap'

def minVal(myList):   #find min of list
    
    minValue = myList[0]    # set minimum to first item in the list
    for i in myList:
        if i < minValue:
            minValue = i
    return minValue

def getTimeZone(latitude,longitude,timestamp):          #routine to return time zone
                                                        # timestamp needs to be a tuple
    # takes lat/lon and time
    # returns time zone name and GMT adjustment

    # print latitude,longitude,timestamp

    api_response = requests.get('https://maps.googleapis.com/maps/api/timezone/json?location={0},{1}&timestamp={2}&key={3}'.format(latitude,longitude,timestamp,api_key))
    api_response_dict = api_response.json()

    if api_response_dict['status'] == 'OK':
        #timezone_id = api_response_dict['timeZoneId']
        timezone_name = api_response_dict['timeZoneName']
        delta = (api_response_dict['rawOffset'])/3600
        dstOffset = api_response_dict['dstOffset']/3600
        GMTtoLocal = delta+dstOffset
        #print api_response_dict
        #print api_response_dict.keys()
        #print 'Timezone ID:', timezone_id
        print 'Timezone Name (GMT Offset):', timezone_name,  '(' + str(GMTtoLocal) + ')'
        # print 'time stamp' , timestamp
        # print 'GMT delta =', delta
        # print 'DST offset = ', dstOffset
        #GMTtoLocal = delta+dstOffset
#    return timezone_name , GMTtoLocal       #return name of time zone and offset from GMT
        GmtOffset = timedelta(hours=GMTtoLocal)  #convert GMT offset to hours
        return GmtOffset
#        return GMTtoLocal       #return offset from GMT


def getLocation(latitude,longitude):

    # takes lat / lon
    # returns street address 

    maps_key ='[enter you google map key here]'     #used for geocoding
    #print "get location function"

    timezone_base_url = 'https://maps.googleapis.com/maps/api/geocode/xml'
        # This joins the parts of the URL together into one string.
    url = timezone_base_url + '?' + urllib.urlencode({
        
        'latlng': "%s,%s" % (latitude,longitude),
        'key': maps_key,
    })
    
    response = str(urllib2.urlopen(url).read())
    soup = BeautifulSoup(response, 'html.parser')          #html got all the data.  lxml only recieved 200 records


    #print soup.prettify()
    #position = soup.findAll('formatted_address')
    #for g in position:
    #    print g
    location = soup.find('formatted_address').text      #extract the text from the tag
    
    #location = soup.find(text='formatted_address: ')
    location = location.replace(',', ' -')  # need to replace , when saving data to csv file
    print location
    return location


def writeKmlFile(data,localTime):

    # data is list with lat, long and status (start, ride or end)


    kml = simplekml.Kml()               # open kml document
#    print "time stamp" , timestamp

    waveline =[]

    for row in data:
            # print 'row = ' , row
            for wave in row:
        
                lat = float(wave[0])
                lon = float(wave[1])
                name = wave[2]
                # line = [waveNumber,lon,lat,name]
                line = [lon,lat]  
                # print line
                waveline.append(line)           #append elements to list named waveline
                if name == "start":
                    waveName = wave[3]          #name each wave as start time
                if name == "end":

                    # print waveline

                    ls = kml.newlinestring(name=waveName)
                    ls.coords = waveline
                    ls.extrude = 1
                    ls.altitudemode = simplekml.AltitudeMode.relativetoground
                    ls.style.linestyle.width = 3
                    ls.style.linestyle.color = simplekml.Color.blue


                    
                    waveline =[]

            
            
    # format local time to use as string name for kml file

    localTime = localTime.strftime("%Y %m %d - %H %M %S")
    # print localTime
  
    fileName = 'I:/Python27/files/garmin/temp/kml/' + localTime + '.kml'
    kml.save(fileName)


def processFile(file_name):

    # main function

    # takes fit file
    # grabs summary data from session message
    # calls function to extract raw data
    # calls function to extract wave data from raw data
    
    myFitFile = FitFile(file_name)
    for record in myFitFile.get_messages('session') :

            factor = (180/pow(2.0,31))  #convert raw lat/long data to decimal

#            print record.get('sport')
            # print record.get('start_time')
            print record.get('wavenum')


            # grab & print summary data

            for field in record :  # print out all the header data
            
##                print field.name, field
                if field.name == 'start_position_lat':
                    start_lat = field.value *factor
                    #print "start lat = ", start_lat
                if field.name == 'start_position_long':
                    start_lon = field.value *factor
                    #print "start lon = ", start_lon
                if field.name == 'start_time':           #need to grab here to get the timezone
                    timestamp=field.value
                    #print "date/time = ", timestamp
                    

            # get street address for given lat/lon

            location = getLocation(start_lat,start_lon)

            # Get local time to name KML file
            # Get delta between GMT and location in order to convert to local time 
            
            timeStampTuple = time.mktime(timestamp.timetuple())                     # need date/time in tuple format
                                                                                    # need date/time to account for daylight savings time

            tzOffset = getTimeZone(start_lat,start_lon,timeStampTuple)  # feed lat, lon and start time to google API to get GMT offset

            localTime = timestamp + tzOffset                #convert to local time
            print 'Local Date & Time = ', localTime


    rawData = getRecordData(myFitFile, tzOffset)  # get raw data from fitfile 
    waves = extractWaves(rawData,location) # process the raw data to determine individual waves
    writeKmlFile(waves,localTime)     # write kml file from the wave data
      

def getRecordData(myFitFile,tzOffset):

    # takes fit file and GMT offset
    # 
    # Get all data messages that are of type record

    # extract desired fileds from the record
    # and return the list
    factor = (180/pow(2.0,31))
    rawData =[]
    for record in myFitFile.get_messages('record'):

        # print ' ----- '

        # time and distance are in every record
        timestamp = record.get('timestamp').value

#        timezone = timedelta(hours=GMTtoLocal)
        # print 'time stamp , zone ',timestamp, timezone
        timestamp = timestamp + tzOffset    #convert to local time

        distance = record.get('distance').value

        #speed, lat and long are all present if in a record

        if record.get('position_lat') != None:  # if record exists then set lat , lon
            lat = record.get('position_lat').value *factor
            lon = record.get('position_long').value *factor
            speed = record.get('speed').value
        else:
            lat =lon = speed = 0




        # print  timestamp.strftime("%H:%M:%S"), distance, speed, lat,lon
#        listEntry = [timestamp.strftime("%H:%M:%S"),distance,speed,lat,lon]
        listEntry = [timestamp,distance,speed,lat,lon]        
        rawData.append(listEntry)

    return rawData # returns a list of records with the desired fields


def extractWaves(rawData,location):
    # print "starting extract waves"

    # takes rawdata [timestamp,distance,speed,lat,lon]
    # returns waveLog [list of waves]
    waveLog = []    #list [lat, long, status, time] to stuff individual ride data that meets speed (min and max), and time criteria
    tempWaveLog =[] #list to capture individual wave meeting min speed and time criteria
                    #then check for maxspeed criteria and append to waveLog if met

    ride = False            # starting out not on a wave
    #speed = 9              # speed threshold for determining if riding a wave (kph)
    minSpeed = 2.5          # meters per second 2.5 mps = 9 kph
    length  = 6             # time threshold for length of ride (seconds)
    s = 2                   # position of speed data in the list
    maxSpeed = 3.611
    maxSpeedValue = 0       #initialize max speed as zero
    totalDistance = 0
    totalTime = 0
    #print "test test" , len(rawData)
    print 'opening csv file '
    waveLogFile = open("I:/Python27/files/garmin/temp/WaveLog.csv","a+")

##    for a in range(0, len(rawData)- length):
##      print rawData[a]


    for a in range(0, len(rawData)- length):                            # for each data set in the list
         

        wave_time =  rawData[a][0]
        #print 'raw data ', rawData[a][0],rawData[a][1],rawData[a][2],rawData[a][3]
        if ride == True:       #                                         #if on a wave, still going?  check speed and gps on next data point
            #print 'ride = true'
            #print rawData[a+1][s]
            #print "rawData[a+1][s] >= minSpeed and rawData[a+1][3]", rawData[a+1][s], minSpeed , rawData[a+1][3] 
            if rawData[a+1][s] >= minSpeed and rawData[a+1][3] != 0:             # next data set meets minSpeed threhold and lat data point [3] != 0 so ride continues
                #print 'rawData[a+1][s] >= minSpeed and rawData[a+1][3] != 0 = true'
                totalTime += 1
                #print "minSpeed = ", rawData[a+1][s], "lat = ", rawData[a+1][3]
                 
                #print "ride ", rawData[a][0], rawData[a][1],rawData[a][2],rawData[a][3], rawData[a][4]
                print "ride ", wave_time.strftime("%H:%M:%S"), rawData[a][1],rawData[a][2],rawData[a][3], rawData[a][4]
#                print "time = " , wave_time.strftime("%H:%M:%S")
                if rawData[a][2] > maxSpeedValue:           #set max speed so far
                    maxSpeedValue = rawData[a][2]
                l =[rawData[a][3],rawData[a][4], "ride", wave_time.strftime("%H:%M:%S")]
                #print l
                #writer.writewave(l)
                tempWaveLog.append(l)
            else:                                           #minSpeed of next rawData point is below threshold so ride ends on this rawData set
                print "end  ", wave_time.strftime("%H:%M:%S"), rawData[a][1],rawData[a][2],rawData[a][3] , rawData[a][4]  
                l =[rawData[a][3],rawData[a][4], "end" , wave_time.strftime("%H:%M:%S")]
                totalDistance = rawData[a][1] - startDistance
                totalTime += 1
                if rawData[a][2] > maxSpeedValue:           #set max speed so far
                    maxSpeedValue = rawData[a][2]
    #            totalTime = subtractTime(startTime,rawData[a][0])


                # writer.writerow(l)
                tempWaveLog.append(l)

               

                ride = False
                # check to see if max speed criteria met
                #print 'ride has ended check max speed value =', maxSpeedValue
                if maxSpeedValue >= maxSpeed:

                    totalDistanceFormat = str(Decimal(totalDistance).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
                    maxSpeedFormat      = str(Decimal((maxSpeedValue *3.6)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
                    totalTimeFormat     = str(timedelta(seconds=totalTime))
                    lineInput = startTime.strftime("%Y %m %d") + "," + startTime.strftime("%H:%M:%S") + "," + location  +  "," + totalDistanceFormat + "," + totalTimeFormat + "," + maxSpeedFormat
    ###                lineInput = adjdate.strftime("%Y %m %d") + "," + location + "," + WStime+ "," + totalDistanceFormat + "," + totalTime + "," + maxSpeedFormat
                    print "line input = ", lineInput
                    waveLogFile.write(lineInput)
                    waveLogFile.write("\n")
                    
                    waveLog.append(tempWaveLog)     #for good waves, append data to waveLog file
                    # print 'wave log = ', tempWaveLog


                    tempWaveLog=[]
                else: 
                    print "max speed not reached",  maxSpeedValue
                    tempWaveLog=[]
                maxSpeedValue = 0           #reset max speed
                totalTime = 0               #reset wave ride time

                # print totalDistance, totalTime
                
        elif ride == False:                                             # if not on a wave, did one just start?
            r=[]                                                        # array of 'length" data points used to check if wave met threshold for time. 
            for g in range(a, a+ length):                               # grab next "length" data points where length = # of seconds 
            #print r
                r.append(rawData[g][s])                                     # stuff into list r


            if minVal(r) >= minSpeed:                                      # minSpeed needs to be above threshold for length of time
                ride = True                                             # if true then start recording wave rawData
                print "start", wave_time.strftime("%H:%M:%S"), rawData[a][1],rawData[a][2],rawData[a][3] , rawData[a][4] 
                startTime = rawData[a][0]                               # start the timer counter
                startDistance = rawData[a][1]                           # start the distance counter
#                l =[ rawData[a][3],rawData[a][4],"start"]
                l =[ rawData[a][3],rawData[a][4],"start", wave_time.strftime("%H:%M:%S")]
                #writer.writerow(l)
                tempWaveLog.append(l)


    waveLogFile.close()
    #print 'waveLog = ' , waveLog
    return waveLog


        
## main program

## for each file in the directory
## run process file function
## 
        


#filename = 'I:/Python27/files/garmin/surf/fit files/in process/2992887515.fit'


source = 'I:/Python27/files/garmin/surf/fit files/in process/'


for filename in os.listdir(source):
    #print filename
    processFile(source+filename)
    

