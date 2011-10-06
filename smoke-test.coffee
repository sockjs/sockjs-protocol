#!/usr/bin/env coffee
require("coffee-script")

client = require('./client')
common = require('./common')



url = 'http://localhost:8080/echo'
count = 200
hz = 5
seconds = 5
test = 'idle'
transport = 'xhr_polling'

console.log(' [*] Connecting to ' + url +
            ' (connections:' + count +
            ', test:' + test + ', transport:' + transport + ')')

connected_counter = 0
connected = ->
    connected_counter += 1
    if connected_counter is count
        console.log(' [*] All connected. Starting')
        for conn in conns
            conn()

closed_counter = 0
closed = ->
    closed_counter += 1
    if closed_counter is count
        console.log(' [*] Done. avg=', stats.avg(),
                    ' dev=', stats.dev(),
                    ' (' + stats.count + ' data points)')

now = ->
    (new Date()).getTime()

stats = new common.StdDev()

conns = for i in [0...count]
    do (i) ->
        c = seconds * hz
        conn = new client.XhrPollingClient(url)
        conn.on('open', connected)
        conn.on 'message', (t0) ->
            c -= 1
            delay = now() - Number(t0)
            stats.add(delay)
            if c > 0
                go = -> conn.send('' + now())
                setTimeout(go, 1000/hz)
            else
                closed()
                conn.close()
        conn.on 'close', -> console.log('ERROR')
        return ->
            conn.send('' + now())


