import sys
import socket
import re
import os
import math
from time import sleep
from Queue import Queue
import thread
from threading import Thread, Lock

# return an error code and message to the user
def error(conn, errno, errmsg):
    print "Sent: Error " + str(errno) + " [" + str(errmsg) + "]"
    return_msg(conn, "ERROR_CODE: " + str(errno) + "\nERROR_DESCRIPTION: " + str(errmsg))

# message the user and append with line break
def return_msg(conn, msg):
    if conn:
        conn.sendall(msg + "\n")

# from http://code.activestate.com/recipes/577187-python-thread-pool/
class Worker(Thread):
    """Thread executing tasks from a given tasks queue"""
    def __init__(self, workers):
        print "Worker Created!"
        Thread.__init__(self)
        # store clients queue pointer
        self.workers = workers
        # set as daemon so it dies when main thread exits
        self.daemon = True
        # start the thread on init
        self.start()

    # function run when thread is started
    def run(self):
        while True:
            # pop an element from the queue
            (conn, addr) = self.workers.get()
            # check if connection or kill request
            if conn:
                self.process_req(conn, addr)
            else:
                break;
            # set task as done in queue
            self.workers.task_done()

    # function to process a client request
    def process_req(self, conn, addr):
        while conn:
            msg = ""
            # Loop through message to receive data
            while "\n\n" not in msg:
                data = conn.recv(4096)
                msg += data
                if len(data) < 4096:
                    break
            # only begin matching when length > 0
            if len(msg) > 0:
                # match different message types
                matchhelo = re.match("HELO ?(.*)\\n", msg)
                matchjoin = re.match("JOIN_CHATROOM: ?(.*)\\nCLIENT_IP: ?(.*)\\nPORT: ?(.*)\\nCLIENT_NAME: ?(.*)\\n", msg)
                matchchat = re.match("CHAT: ?(.*)\\nJOIN_ID: ?(.*)\\nCLIENT_NAME: ?(.*)\\nMESSAGE: ?(.*)\\n\\n", msg)
                matchleave = re.match("LEAVE_CHATROOM: ?(.*)\\nJOIN_ID: ?(.*)\\nCLIENT_NAME: ?(.*)\\n", msg)
                matchdisconnect = re.match("DISCONNECT: ?(.*)\\nPORT: ?(.*)\\nCLIENT_NAME: ?(.*)\\n", msg)
        
                # do certain actions depending on message type
                if msg == "KILL_SERVICE\n":
                    os._exit(1)
                elif matchjoin is not None:
                    self.join_chatroom(matchjoin.groups()[0], matchjoin.groups()[3], conn)
                elif matchchat is not None:
                    self.send_message(matchchat.groups()[0], matchchat.groups()[1], matchchat.groups()[2], matchchat.groups()[3], conn)
                elif matchleave is not None:
                    self.leave_chatroom(matchleave.groups()[0], matchleave.groups()[1], matchleave.groups()[2], conn)
                elif matchhelo is not None:
                    return_msg(conn, "HELO " + matchhelo.groups()[0] + "\nIP:" + my_ip + "\nPort:" + str(sport) + "\nStudentID:" + studentid + "\n")
                elif matchdisconnect is not None:
                    self.disconnect(matchdisconnect.groups()[2], conn)
                    conn.shutdown(1)
                    conn.close()
                    break
                else:
                    error(conn, 0, "Unknown Message Received")
        print (matchdisconnect.groups()[2] if matchdisconnect is not None else "Unknown") + " Socket Disconnected"
    
    def join_chatroom(self, room_name, user_nick, conn):
        room = None
        room_id = str(hash(room_name))
        join_id = str(hash(user_nick))
        # acquire chatrooms mutex to access global room data
        chatrooms_mutex.acquire()
        try:
            # create chatroom if it does not already exist
            if room_id not in chatrooms:
                chatrooms[room_id] = Chatroom(room_name)
            room = chatrooms[room_id]
        finally:
            chatrooms_mutex.release()
        print "Receieved: JOIN " + room.name + " from " + user_nick
        room.add_user(join_id, user_nick, conn)

    def send_message(self, room_id, join_id, user_nick, msg, conn):
        room = None
        # acquire chatrooms mutex to access global room data
        chatrooms_mutex.acquire()
        try:
            # check if destination chatroom exists
            if room_id not in chatrooms:
                error(conn, 1, "Chatroom not found")
                return
            room = chatrooms[room_id]
        finally:
            chatrooms_mutex.release()
        print "Receieved: CHAT " + room.name + "(" + msg + ") from " + user_nick
        room.chat(user_nick, msg)

    def leave_chatroom(self, room_id, join_id, user_nick, conn):
        room = None
        # acquire chatrooms mutex to access global room data
        chatrooms_mutex.acquire()
        try:
            # check if destination chatroom exists
            if room_id not in chatrooms:
                error(conn, 1, "Chatroom not found")
                return
            room = chatrooms[room_id]
        finally:
            chatrooms_mutex.release()
        print "Receieved: LEAVE " + room.name + " from " + user_nick
        room.remove_user(join_id, user_nick, conn)
    
    def disconnect(self, user_nick, conn):
        rooms = []
        print "Receieved: DISCONNECT from " + user_nick
        # acquire chatrooms mutex to access global room data
        chatrooms_mutex.acquire()
        try:
            # cache list of all chatroom objects
            rooms = chatrooms.values()
        finally:
            chatrooms_mutex.release()
        for r in rooms:
            r.disconnect_user(user_nick, conn)

class Chatroom:
    """Represent chatroom that clients can join"""

    def __init__(self, name):
        # save name and id of room name
        self.name = name
        self.id = str(hash(name))
        self.clients = {}
        self.mutex = Lock()

    def add_user(self, join_id, user_nick, conn):
        # acquire clients mutex before accessing
        self.mutex.acquire()
        try:
            # add client to clients list
            self.clients[join_id] = (user_nick, conn)
        finally:
            self.mutex.release()
        # send joined chatroom message to user
        return_msg(conn, "JOINED_CHATROOM: " + self.name + "\nSERVER_IP: " + str(my_ip) + "\nPORT: " + str(sport) + 
            "\nROOM_REF: " + str(self.id) + "\nJOIN_ID: " + str(join_id))
        print "Sent: JOINED " + self.name + " to " + user_nick
        # send joined message to all members in chatroom
        self.chat(user_nick, user_nick + " has joined this chatroom.")

    def chat(self, source_nick, msg):
        # save connected users in room
        conns = []
        # acquire clients mutex before accessing
        self.mutex.acquire()
        try:
            # add all client connections to cached list
            conns = self.clients.values()
        finally:
            self.mutex.release()
        # send chat message to every user in room
        for dest_nick, dest_conn in conns:
            print "\"" + msg + "\" to " + dest_nick + " in " + self.name
            return_msg(dest_conn, "CHAT:" + str(self.id) + "\nCLIENT_NAME:" + source_nick + "\nMESSAGE:" + msg + "\n")

    def remove_user(self, join_id, user_nick, conn):
        # send left chatroom response to user whether removed or not
        return_msg(conn, "LEFT_CHATROOM: " + str(self.id) + "\nJOIN_ID: " + str(join_id))
        print "Sent: LEFT " + self.name + " to " + user_nick
        # send left message to all members in chatroom
        self.chat(user_nick, user_nick + " has left this chatroom.")
        # acquire clients mutex before accessing (after sent leave msgs)
        self.mutex.acquire()
        try:
            # remove client from clients list if exists
            if join_id in self.clients:
                if self.clients[join_id][0] == user_nick:
                    del self.clients[join_id]
                else:
                    error(conn, 3, "Nick does not match server join id")
                    return
        finally:
            self.mutex.release()
    
    def disconnect_user(self, user_nick, conn):
        join_id = str(hash(user_nick))
        # acquire clients mutex to check if user in room
        self.mutex.acquire()
        try:
            # check if client is member of room
            if join_id not in self.clients:
                return
        finally:
            self.mutex.release()
        # send disconnect message to all members in chatroom
        self.chat(user_nick, user_nick + " has left this chatroom.")
        # acquire clients mutex to remove user from room
        self.mutex.acquire()
        try:
            # delete from clients array
            del self.clients[join_id]
        finally:
            self.mutex.release()

# find public ip address
# (from http://stackoverflow.com/a/9481595)
from urllib2 import urlopen
my_ip = urlopen('http://ip.42.pl/raw').read()
print my_ip

# global variables
sip = ''
sport = 0
studentid = 'f01f3533cd97ebd24e7c1b49639a2c3c2fd904c9e6a105226ecde32db16d0b10'

# queue object to store requests
workers = Queue()

# chatrooms object and counters to store chatroom data
chatrooms = {}
chatrooms_mutex = Lock()

def main():
    global sip, sport
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit("Port number required")

    # create socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # max and min number of threads
    max_threads = 100.0
    min_threads = 10.0

    # thread counter
    num_threads = min_threads

    # queue threshold to increase or decrease num workers
    queue_threshold = 50.0

    # bind to port and listen for connections
    s.bind(("0.0.0.0", int(sys.argv[1]))) 
    s.listen(5)
    sip, sport = s.getsockname()

    # create initial workers
    for _ in range(int(min_threads)): 
        Worker(workers)

    # continuous loop to keep accepting requests
    while 1:
        # accept a connection request
        conn, addr = s.accept()

        # cache queue size and get threshold
        qsize = workers.qsize()
        queue_margin = int(math.ceil(num_threads * (queue_threshold / 100.0)))

        # check if queue size is between num_threads and (num_threads - margin)
        if qsize >= (num_threads - queue_margin) and num_threads != max_threads:
            # add queue_margin amount of new workers
            for _ in range(queue_margin): 
                if num_threads == max_threads:
                    break
                Worker(workers)
                num_threads += 1
        # else check if queue size is between 0 and margin
        elif qsize <= queue_margin and num_threads != min_threads:
            # remove queue_margin amount of workers
            for _ in range(queue_margin): 
                if num_threads == min_threads:
                    break
                clients.put((None, None))
                num_threads -= 1

        # receive data and put request in queue
        workers.put((conn, addr))

if __name__ == "__main__": main()