#!/usr/bin/env python3
import time
import threading
import queue
import PhoneTree
import PhoneAction


def listen_for_input(q):
    while True:
        user_input = input("Your choice: ")
        q.put(user_input)


def start_listening_for_input(q):
    thrd = threading.Thread(target=listen_for_input, args=(q,))
    thrd.daemon = True
    thrd.start()


def sales_rep_action(sales_menu: PhoneTree):
    print("Pricing information coming right up!")
    sales_rep = PhoneTree.PhoneTree("Sales rep coming right up! press 1")
    sales_rep.navigate()
    return True

def phone_tree(q):
    sales = PhoneTree.PhoneTree( "To talk to a sales rep, press 1. For pricing, press 2.")
    sales.action = lambda: sales_rep_action(sales)
    support = PhoneTree.PhoneTree( "For technical support, press 1. For customer service, press 2.")
    return PhoneTree.PhoneTree( "For Sales, press 1. For Support, press 2.", options={"1": sales, "2": support}, input_queue=q)


def main():
    q = queue.Queue()
    start_listening_for_input(q)
    main_menu = phone_tree(q)
    print(f"PhoneTree: {main_menu}")
    main_menu.navigate(main_menu)


if __name__ == "__main__":
    print("Welcome to the phone tree system!")
    time.sleep(1)
    main()
