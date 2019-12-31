#!/usr/bin/python3

# This method will spin up threads and process IP addresses in a queue

# Importing Netmiko modules
from netmiko import Netmiko
from netmiko.ssh_exception import NetMikoAuthenticationException, NetMikoTimeoutException

# Additional modules imported for getting password, pretty print
from getpass import getpass
from pprint import pprint
import signal,os

# Queuing and threading libraries
from queue import Queue
import threading


# These capture errors relating to hitting ctrl+C (I forget the source)
signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # IOError: Broken pipe
signal.signal(signal.SIGINT, signal.SIG_DFL)  # KeyboardInterrupt: Ctrl-C

# Get the password
password = getpass()

# Switch IP addresses from text file that has one IP per line
ip_addrs_file = open('ips.txt')
ip_addrs = ip_addrs_file.read().splitlines()

# Set up thread count for number of threads to spin up
num_threads = 8
# This sets up the queue
enclosure_queue = Queue()
# Set up thread lock so that only one thread prints at a time
print_lock = threading.Lock()

# CLI command being sent. This could be anywhere (and even be a passed paramenter) 
# but I put at the top for code readability
command = "show inventory"

# Function used in threads to connect to devices, passing in the thread # and queue
def deviceconnector(i,q):

    # This while loop runs indefinitely and grabs IP addresses from the queue and processes them
    # Loop will stop and restart if "ip = q.get()" is empty
    while True:
        
        # These print statements are largely for the user indicating where the process is at
        # and aren't required
        print("{}: Waiting for IP address...".format(i))
        ip = q.get()
        print("{}: Acquired IP: {}".format(i,ip))
        
        # k,v passed to net_connect
        device_dict =  {
            'host': ip,
            'username': 'jimmy',
            'password': password,
            'device_type': 'cisco_ios'
        }

        # Connect to the device, and print out auth or timeout errors
        try:
            net_connect = Netmiko(**device_dict)
        except NetMikoTimeoutException:
            with print_lock:
                print("\n{}: ERROR: Connection to {} timed-out.\n".format(i,ip))
            q.task_done()
            continue
        except NetMikoAuthenticationException:
            with print_lock:
                print("\n{}: ERROR: Authenticaftion failed for {}. Stopping script. \n".format(i,ip))
            q.task_done()
            os.kill(os.getpid(), signal.SIGUSR1)

        # Capture the output, and use TextFSM (in this case) to parse data
        output = net_connect.send_command(command,use_textfsm=True)
        
        with print_lock:
            print("{}: Printing output...".format(i))
            pprint(output)

        # Disconnect from device
        net_connect.disconnect

        # Set the queue task as complete, thereby removing it from the queue indefinitely
        q.task_done()

# Mail function that compiles the thread launcher and manages the queue
def main():

    # Setting up threads based on number set above
    for i in range(num_threads):
        # Create the thread using 'deviceconnector' as the function, passing in
        # the thread number and queue object as parameters 
        thread = threading.Thread(target=deviceconnector, args=(i,enclosure_queue,))
        # Set the thread as a background daemon/job
        thread.setDaemon(True)
        # Start the thread
        thread.start()

    # For each ip address in "ip_addrs", add that IP address to the queue
    for ip_addr in ip_addrs:
        enclosure_queue.put(ip_addr)

    # Wait for all tasks in the queue to be marked as completed (task_done)
    enclosure_queue.join()
    print("*** Script complete")

if __name__ == '__main__':
    
    # Calling the main function
    main()
