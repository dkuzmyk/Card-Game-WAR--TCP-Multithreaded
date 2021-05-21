"""
war card game client and server
"""
import asyncio
from collections import namedtuple
from enum import Enum
import logging
import random
import socket
import socketserver
import _thread
import sys

"""
Namedtuples work like classes, but are much more lightweight so they end
up being faster. It would be a good idea to keep objects in each of these
for each game which contain the game's state, for instance things like the
socket, the cards given, the cards still available, etc.
"""
# keep Game object with the following info: sock1, sock2, game number, p1 cards, p2 cards
Game = namedtuple("Game", ["p1", "p2", "gm", "p1_c", "p2_c"])
games = []  # global variable so that all async tasks can access it ### Now useless, replaced with a better method

# keep track of current hands for all games: p_hand[game number], reset after every return message
p1_hand = []
p2_hand = []
cards_played = []  # keep track of played cards, detect duplicates


class Command(Enum):
    """
    The byte values sent as the first byte of any message in the war protocol.
    """
    WANTGAME = 0
    GAMESTART = 1
    PLAYCARD = 2
    PLAYRESULT = 3


class Result(Enum):
    """
    The byte values sent as the payload byte of a PLAYRESULT message.
    """
    WIN = 0
    DRAW = 1
    LOSE = 2


def readexactly(sock, numbytes):
    """
    Accumulate exactly `numbytes` from `sock` and return those. If EOF is found
    before numbytes have been received, be sure to account for that here or in
    the caller.
    """
    try:
        msg = sock.recv(numbytes)  # read current socket
        # print('raw msg', msg)
        type_msg = msg[0]  # scrap message type type: Commands
        r = msg[1:]  # actual message
        '''
        if numbytes == 27:                      # in case it's arriving a hand, not actually used since clients have 
            pog = []                            # their own readexactly
            for i in r:
                pog.append(i)
        else:
            pog = r[0]
        '''
        pog = r[0]
        return type_msg, pog
    except:
        print("Extraction problem from readexactly.")


def kill_game(game):
    """
    TODO: If either client sends a bad message, immediately nuke the game.
    """
    # close sockets of game
    game.p1.close()
    game.p2.close()
    print('Game', game.gm, 'killed.')


def compare_cards(card1, card2):
    """
    TODO: Given an integer card representation, return -1 for card1 < card2,
    0 for card1 = card2, and 1 for card1 > card2
    """
    # mapping for debug
    card_map = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']

    # cards 0..51 need to be referenced by their value for every suit, not their order 0..51
    if card1 >= 13:
        card1 = card1 % 13
    if card2 >= 13:
        card2 = card2 % 13

    print('Comparing p1: {} with p2: {}'.format(card_map[card1], card_map[card2]))  # debug and server purposes

    # compare the true value of cards
    if card1 < card2:
        return -1
    elif card1 == card2:
        return 0
    elif card1 > card2:
        return 1
    else:
        print('Error in comparing cards, card1 or card2 is not an integer.')


def deal_cards():
    """
    TODO: Randomize a deck of cards (list of ints 0..51), and return two
    26 card "hands."
    """
    # create an ordered deck, shuffle the deck and return the two hands
    deck = list(range(0, 52))
    random.shuffle(deck)
    hand1 = deck[:26]
    hand2 = deck[26:]
    return hand1, hand2


# useful function to convert a list into a string of bytes
def list_to_bytes(l):
    r = b''
    for e in l:
        r += bytes([e])
    return r


# handle the already established connections, read messages in, write messages out
def handler(sock, g, m, addr):
    while True:
        try:
            type_msg, msg = readexactly(sock, 2)
            # print('type msg', type_msg)  # debug
        except Exception:
            print('One client disconnected.')
            kill_game(g)
            _thread.exit()
            break

        # collect receiving card
        if type_msg == Command.PLAYCARD.value:
            m.acquire()  # lock thread so that threads don't interfere with the writing/updating

            # TODO check if card sent is within player's allowed deck --> DONE
            # TODO check if card is not a duplicate --> DONE
            # TODO close threads for clients when a game is over --> DONE

            # check if g is not buggy,
            # check what player is current (p1 or p2),
            # check if card played is within its cards
            # check if card played was not already played before in cards_played
            if g is not None and g.p1 == sock and msg not in cards_played[g.gm]:
                if msg in g.p1_c:
                    p1_hand[g.gm] = msg             # add card to current card played
                    cards_played[g.gm].append(msg)  # if card is not illegal, add to played cards
                else:
                    kill_game(g)
                    print("Client sent a card it's not supposed to have.")

            elif g is not None and g.p2 == sock and msg not in cards_played[g.gm]:
                if msg in g.p2_c:
                    p2_hand[g.gm] = msg
                    cards_played[g.gm].append(msg)
                else:
                    kill_game(g)
                    print("Client sent a card it's not supposed to have.")

            if g is not None and (p1_hand[g.gm] != -1 and p2_hand[g.gm] != -1):

                r = compare_cards(p1_hand[g.gm], p2_hand[g.gm])
                if r == 1:
                    print('p1 wins')
                    g.p1.send(bytes([Command.PLAYRESULT.value]) + bytes([Result.WIN.value]))
                    g.p2.send(bytes([Command.PLAYRESULT.value]) + bytes([Result.LOSE.value]))
                elif r == -1:
                    print('p2 wins')
                    g.p1.send(bytes([Command.PLAYRESULT.value]) + bytes([Result.LOSE.value]))
                    g.p2.send(bytes([Command.PLAYRESULT.value]) + bytes([Result.WIN.value]))
                else:
                    print('draw')
                    g.p1.send(bytes([Command.PLAYRESULT.value]) + bytes([Result.DRAW.value]))
                    g.p2.send(bytes([Command.PLAYRESULT.value]) + bytes([Result.DRAW.value]))

                # reset hands
                p1_hand[g.gm] = -1
                p2_hand[g.gm] = -1

            m.release()
        else:
            kill_game(g)
            print('Client {} sent a message with code: {}'.format(addr, type_msg))
        # TODO for all games, if game.p1_current and game.p1_current not -1, calculate who won and set to -1 then respond DONE
        # TODO check all clients, if client responds with b"", close game and connected clients DONE


def serve_game(host, port):
    """
    TODO: Open a socket for listening for new connections on host:port, and
    perform the war protocol to serve a game of war between each client.
    This function should run forever, continually serving clients.
    """
    clients = []  # keep a list of clients that have connected, not useful anymore
    clients_want_game = []  # keep a list of clients that want a game

    # server connection
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen()
    game_counter = 0  # keep track of how many games are played
    m = _thread.allocate_lock()  # thead lock
    while True:
        client_id, addr = server.accept()
        print('Client with address {} connected.'.format(addr))
        # clients.append(client_id)  # DEPRECATED, now a waste of memory

        type_msg, msg = readexactly(client_id, 2)  # read first message, if type == Command.WANTGAME.value then OK
        print('type msg', type_msg)

        # add the current client to the list of clients that want a game
        if type_msg == Command.WANTGAME.value:
            clients_want_game.append(client_id)
        else:
            client_id.close()
            print('Client {} connected without WANTGAME byte'.format(addr))

        # if there's at least 2 clients waiting for a game, make a game
        if len(clients_want_game) >= 2:
            hand1, hand2 = deal_cards()  # get hands
            g = Game(p1=clients_want_game[0], p2=clients_want_game[1], gm=game_counter, p1_c=hand1, p2_c=hand2)
            # games.append(g)  # save the ongoing game in a list. DEPRECATED

            # make room for the hands of individual players. p1_hands[game.gm] = player 1 hand at game=n
            p1_hand.append(-1)
            p2_hand.append(-1)
            cards_played.append([])  # list of total cards played, for duplicate check

            # remove the clients from the queue
            clients_want_game.remove(clients_want_game[1])
            clients_want_game.remove(clients_want_game[0])

            # send hands to clients # TODO: fix size of bytes overflow DONE
            g.p1.send((bytes([Command.GAMESTART.value]) + list_to_bytes(g.p1_c)))
            g.p2.send((bytes([Command.GAMESTART.value]) + list_to_bytes(g.p2_c)))

            # print(list_to_bytes(g.p1_c))
            # print(list_to_bytes(g.p2_c))

            _thread.start_new_thread(handler, (g.p1, g, m, addr))  # create a new thread to manage that client
            _thread.start_new_thread(handler, (g.p2, g, m, addr))  # create a new thread to manage that client
            print('Starting game', g.gm)
            game_counter += 1

        print('Clients in queue:', len(clients_want_game))


async def limit_client(host, port, loop, sem):
    """
    Limit the number of clients currently executing.
    You do not need to change this function.
    """
    async with sem:
        return await client(host, port, loop)


async def client(host, port, loop):
    """
    Run an individual client on a given event loop.
    You do not need to change this function.
    """
    try:
        reader, writer = await asyncio.open_connection(host, port, loop=loop)
        # send want game
        writer.write(b"\0\0")
        card_msg = await reader.readexactly(27)
        #print(card_msg)
        myscore = 0
        for card in card_msg[1:]:
            #print(card)
            writer.write(bytes([Command.PLAYCARD.value, card]))
            result = await reader.readexactly(2)
            if result[1] == Result.WIN.value:
                myscore += 1
            elif result[1] == Result.LOSE.value:
                myscore -= 1
        if myscore > 0:
            result = "won"
        elif myscore < 0:
            result = "lost"
        else:
            result = "drew"
        logging.debug("Game complete, I %s", result)
        writer.close()
        return 1
    except ConnectionResetError:
        logging.error("ConnectionResetError")
        return 0
    except asyncio.streams.IncompleteReadError:
        logging.error("asyncio.streams.IncompleteReadError")
        return 0
    except OSError:
        logging.error("OSError")
        return 0


def main(args):
    """
    launch a client/server
    """
    host = args[1]
    port = int(args[2])
    if args[0] == "server":
        try:
            # your server should serve clients until the user presses ctrl+c
            serve_game(host, port)
        except KeyboardInterrupt:
            pass
        return
    else:
        loop = asyncio.get_event_loop()

    if args[0] == "client":
        loop.run_until_complete(client(host, port, loop))
    elif args[0] == "clients":
        sem = asyncio.Semaphore(1000)
        num_clients = int(args[3])
        clients = [limit_client(host, port, loop, sem)
                   for x in range(num_clients)]

        async def run_all_clients():
            """
            use `as_completed` to spawn all clients simultaneously
            and collect their results in arbitrary order.
            """
            completed_clients = 0
            for client_result in asyncio.as_completed(clients):
                completed_clients += await client_result
            return completed_clients

        res = loop.run_until_complete(
            asyncio.Task(run_all_clients(), loop=loop))
        logging.info("%d completed clients", res)

    loop.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(sys.argv[1:])
