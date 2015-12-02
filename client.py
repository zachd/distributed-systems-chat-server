import socket
import sys
from time import sleep
from random import randrange

if len(sys.argv) < 2 or not sys.argv[1].isdigit():
    sys.exit("Port number required")

# set GET message
data1 = "JOIN_CHATROOM: room\nCLIENT_IP: 0\nPORT: 0\nCLIENT_NAME: client\n"
data2 = "CHAT: room\nJOIN_ID: 0\nCLIENT_NAME: client\nMESSAGE: test\n\n"
data3 = "LEAVE_CHATROOM: room\nJOIN_ID: 0\nCLIENT_NAME: client\n"


# connect to socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("localhost", int(sys.argv[1]))) 
s.settimeout(2)

# send data
print "Sent: \"" + data1 + "\""
s.sendall(data1)

# print received response
received = s.recv(2048)
print "Rec: \"{}\"".format(received)

# wait for key press
raw_input("Press Enter to continue...")

# send data
print "Sent: \"" + data2 + "\""
s.sendall(data2)

# print received response
received = s.recv(2048)
print "Rec: \"{}\"".format(received)

# wait for key press
raw_input("Press Enter to continue...")

# send data
print "Sent: \"" + data3 + "\""
s.sendall(data3)

# print received response
received = s.recv(2048)
print "Rec: \"{}\"".format(received)