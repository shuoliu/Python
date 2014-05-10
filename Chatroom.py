#A chat room sample that can be accessed through Telnet
#Supported commands are listed below. ( Ctrl + F -> 'commands =')

import socket
import threading
from os import linesep

THISISYOU = ' (** this is you)'

class Chatroom:
    def __init__(self,  name):
        self.users = {}
        self.name = name
        
    def addUser(self,  user):
        self.users[user.username] = user
        
    def removeUser(self,  user):
        del self.users[user.username]
        
    def getUserCount(self):
        return len(self.users)


class UserTask(threading.Thread):
    commands = {'/rooms':'list all rooms',
                '/users [roomname]':'list users in a specified room or current room. ' +
                '(if not in a room, list all users)',
                '/newroom [roomname]':'create a new room',
                '/join [roomname]':'join a room',
                '/private [username]':'choose a user to send message, user /leave to exit',
                '/leave':'leave a private talk or current room (you can /join another room without /leave)',
                '/quit':'stop the session',
                '/help':'show all commands'}
    def __init__(self,  client,  addr,  users,  chatrooms,  mutex):
        threading.Thread.__init__(self)
        self.client = client
        self.addr = addr
        self.users = users
        self.chatrooms = chatrooms
        self.mutex = mutex
        self.username = ''
        self.chatroom = None
        self.pmuser = None
        self.who_pm_me = []

    def readLine(self, client, size = 1024):
        n = 0;
        receive = []
        while True:
            c = client.recv(1)
            if ++n > size: break
            if c == '\n': break
            receive.append(c)
        if receive[-1] == '\r':
            receive = receive[0:-1]
        return ''.join(receive)
        
    def run(self):
        self.client.sendall('Welcome to this chat server' + linesep)
        #choose name
        while True:
            self.client.sendall('Login Name?' + linesep)
            name = self.readLine(self.client, 16)
            if name.startswith('/'):
                self.client.sendall('Name invalid.' + linesep)
                continue
            if self.createUser(name): break
            self.client.sendall('Sorry, name taken.' + linesep)
        
        self.client.sendall('Welcome ' + self.username + '!' + linesep)
        self.printHelp()
        
        while True:
            receive = self.readLine(self.client)
            #print self.getName() + ' get ' + receive
            self.mutex.acquire()
            if receive.startswith('/'):
                argument = receive.split()
                command = argument[0]
                
                if command == '/rooms':
                    self.listRooms()
                elif command == '/users':
                    if len(argument) > 1:
                        if argument[1] in self.chatrooms:
                            self.listRoomUsers(self.chatrooms[argument[1]])
                        else: self.client.sendall('no such room name ' + argument[1] + linesep)
                    else:
                        self.listRoomUsers(self.chatroom)
                elif command == '/newroom':
                    if len(argument) == 1:
                        self.client.sendall('please give a name' + linesep)
                    else: self.createRoom(argument[1])
                elif command == '/join':
                    if len(argument) == 1:
                        self.client.sendall('please give a name' + linesep)
                    elif argument[1] not in self.chatrooms:
                        self.client.sendall('no such room name: ' + argument[1] + linesep)
                    else: self.joinRoom(self.chatrooms[argument[1]])
                elif command == '/private':
                    if len(argument) == 1:
                        self.client.sendall('please choose a user to send message' + linesep)
                    else:
                        if argument[1] not in self.users or argument[1] == self.username:
                            self.client.sendall('invalid user: ' + argument[1] + linesep)
                        else:
                            self.pmuser = self.users[argument[1]]
                            self.pmuser.who_pm_me.append(self)
                            self.client.sendall('now send message to user: ' + argument[1] + linesep)
                elif command == '/leave':
                    if self.pmuser:
                        self.leavePrivate()
                    elif not self.chatroom:
                        self.client.sendall('you are not in a room' + linesep)
                    else:
                        self.leaveRoom()
                elif command == '/quit':
                    self.leaveRoom()
                    for u in self.who_pm_me:
                        u.client.send('user ' + self.username + ' has left' + linesep)
                        u.leavePrivate()
                    self.client.sendall('BYE' + linesep)
                    del self.users[self.username]
                    self.mutex.release()
                    break;
                elif command == '/help':
                    self.printHelp()
                else: self.client.sendall('no such command: ' + command + linesep)
            else:
                if self.pmuser:
                    self.sendPrivate(receive)
                else:
                    self.sendMessage(receive)
            self.mutex.release()
        self.client.close()

    def printHelp(self):
        for h in self.commands:
            self.client.sendall(h + ': ' + self.commands[h] + linesep)
        
    def createUser(self,  name):
        if name not in self.users:
            self.username = name
            #add into user list
            self.mutex.acquire()
            self.users[name] = self
            self.mutex.release()
            return True
        else: return False
        
    def listRooms(self):
        self.client.sendall('Active rooms are:' + linesep)
        for room in self.chatrooms.values():
            self.client.sendall('* ' + room.name + '(' + str(room.getUserCount()) + ')' + linesep)
        self.client.sendall('end of list.' + linesep)

    def listRoomUsers(self, room):
        if not room:
            users = self.users
        else: users = room.users
        for user in users:
            send = '* ' + user
            if user != self.username:
                self.client.sendall(send + linesep)
            else: self.client.sendall(send + THISISYOU + linesep)
        self.client.sendall('end of list.' + linesep)
        
    def createRoom(self,  roomname):
        if roomname in self.chatrooms:
            self.client.sendall('Sorry, name taken.' + linesep)
        else:
            room = Chatroom(roomname)
            self.chatrooms[roomname] = room
            self.joinRoom(room)
        
        
    def sendMessage(self, message, prefix=True):
        if not self.chatroom:
            self.client.sendall('You must be in a room or send a private message.' + linesep)
            return
        if prefix:
            message = self.username + ': ' + message
        for u in self.chatroom.users.values():
            if(u == self):
                u.client.sendall(message + THISISYOU + linesep)
            else:
                u.client.sendall(message + linesep)
        
        
    def joinRoom(self, room):
        if self.chatroom and room == self.chatroom:
            self.client.sendall('you already in the room: ' + room.name + linesep)
            return
        self.leaveRoom()
        room.addUser(self)
        self.chatroom = room
        self.client.sendall('entering room: ' + room.name + linesep)
        for u in self.chatroom.users.values():
            u.client.sendall(self.username + ' has entered room: ' + room.name + linesep)
        self.listRoomUsers(room)
        
    def leaveRoom(self):
        if self.chatroom:
            self.sendMessage('gotta go!')
            self.sendMessage('* user has left chat: ' + self.username, False)
            self.chatroom.removeUser(self)
            if self.chatroom.getUserCount() == 0:
                del self.chatrooms[self.chatroom.name]
            self.chatroom = None

    def sendPrivate(self, message):
        message = '(PM)' + self.username + ': ' + message
        self.client.send(message + THISISYOU + linesep)
        self.pmuser.client.sendall(message + linesep)

    def leavePrivate(self):
        self.pmuser.who_pm_me.remove(self)
        self.client.sendall('leave private talk' + linesep)
        if self.chatroom:
            self.client.sendall('you now send message to room: ' + self.chatroom.name + linesep)
        self.pmuser = None



if __name__ == "__main__":
    users = {}
    chatrooms = {}
    mutex = threading.Lock()
    
    HOST = ''
    PORT = 1234 #change your port here
    s = socket.socket(socket.AF_INET,  socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen(5)

    print 'start listening'
    
    while True:
        client,  addr = s.accept()
        thread = UserTask(client,  addr,  users,  chatrooms,  mutex)
        thread.start()
