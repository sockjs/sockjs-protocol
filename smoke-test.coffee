#!/usr/bin/env coffee
events = require('events')
http = require('http')
urlparse = require('url').parse


class GenericClient extends events.EventEmitter
    constructor: (url) ->
        @id = ('' + Math.random()).slice(2)
        @url = url + '/0/' + @id
        @buffer = []
        @is_opened = false
        @is_closed = false
        @sending = false
        @_kick_recv()

    _got_message: (msg) ->
        [type, payload] = [msg.slice(0,1), msg.slice(1)]
        switch type
            when 'o'
                if not @is_opened
                    @is_opened = true
                    @emit('open')
                else
                    console.log('Already open')
                    @is_closed = true
                    @emit('close', 1000, 'error')
            when 'h' then null
            when 'a'
                for m in JSON.parse(payload)
                    @emit('message', m)
            when 'c'
                @is_closed = true
                [status, reason] = JSON.parse(payload)
                @emit('close', status, reason)
            else
                throw Error('unknown type ' + type)

    send: (msg) ->
        @buffer.push(msg)
        if not @sending and not @is_closed
            @_kick_send()

    close: () ->
        @is_closed = true

class XhrPollingClient extends GenericClient
    _kick_send: () ->
        @sending = true
        r = POST(@url + '/xhr_send',
                 {'Content-Type': 'application/xml'},
                 JSON.stringify(@buffer))
        @buffer = []
        r.on 'end', () =>
            @sending = false
            if not @is_closed and @buffer.length > 0
                @_kick_send()

    _kick_recv: () ->
        r = POST(@url + '/xhr')
        r.on 'end', (body) =>
            @_got_message(body)
            if not @is_closed
                @_kick_recv()


class HttpRequest extends events.EventEmitter
    constructor: (method, url, headers, body) ->
        u = urlparse(url)
        options =
          host: u.hostname
          port: Number(u.port) or (if u.protocol is 'http:' then 80 else 443)
          path: u.pathname + (if u.query then '?' + u.query else '')
          method: method
          headers: (if headers then headers else {})
          agent: false

        @chunks = []
        @req = http.request options, (@res) =>
            @req.socket.setTimeout(60000)
            @status = @res.statusCode
            @headers = @res.headers
            @res.on 'data', (chunk) =>
                chunk = chunk.toString('utf-8')
                @chunks.push(chunk)
                @emit('chunk', chunk)
            @res.on 'end', =>
                @data = @chunks.join('')
                @emit('end', @data)
            @res.on 'close', =>
                console.log('close')

        @req.on 'error', (e) =>
            console.log('error!',e)
        if body
            @req.write(body, 'utf-8')
        @req.end()

    _on_response: (@res) =>

GET = (url, headers, body) ->
    new HttpRequest('GET', url, headers, body)

POST = (url, headers, body) ->
    new HttpRequest('POST', url, headers, body)


class StdDev
    constructor: ->
        @sum = 0.0
        @sum_sq = 0.0
        @count = 0

    add: (v) ->
        @sum += v
        @sum_sq += v*v
        @count += 1

    avg: () ->
        if @count is 0
            return null
        return @sum / @count

    dev: () ->
        if @count is 0
            return null
        avg = @avg()
        variance = (@sum_sq / @count) - (avg * avg)
        return Math.sqrt(variance)


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

stats = new StdDev()

conns = for i in [0...count]
    do (i) ->
        c = seconds * hz
        conn = new XhrPollingClient(url)
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


