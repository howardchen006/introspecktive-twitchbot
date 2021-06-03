import sqlite3
from twitchio.ext import commands
import datetime

"""
This bot is designed to manage viewer battles for the game Super Smash Bros. Ultimate, which IntroSpecktive plays on stream.
During viewer battles, viewers in the stream register themselves to a line automated by this application, so that
IntroSpecktive can play people in an orderly fashion.
"""

playerqueue = [] # Stores the current list of people in the line.
sublist = [] # On Twitch, channels have both regular viewers and subscribers, the latter being a paid subscription.
# As a way to give back to the subscribers, IntroSpecktive likes to give subscribers priority, hence a separate list for them.
played = set() # Once people have finished their turn, their name will be stored in this set to inhibit them from
# rejoining the list so that more people have a chance to play.
toggles = {'newsubperk':True, 'subsonlymode':False, 'limit':True, 'open':True, 'verbose':True, 'variety': True}
"""
toggles is a dictionary of booleans that is used to enforce restrictions on the list depending on the streamer's ideals.
"newsubperk" is an on switch for the automation of a new subscriber being offered a spot on the list upon their subscription.
"subsonlymode" being True restricts the list to subscribers only when IntroSpecktive feels like playing subscribers only on certain days.
"limit" being True restricts the cardinality of the list to 7 at a time so it doesn't get too large, which can detract viewers.
"open" dictates whether the list is open for joining at a given point in time.
"verbose" was implemented so that selective bot messages can be muted in case viewers spam the bot commands.
"variety" being True means that players who have played within the past week (determined by data within a SQLite3 database) are inhibited from joining, so that different people get a chance to play.
"""
info = {'arenaid': None} # In the game Super Smash Bros. Ultimate, IntroSpecktive creates a lobby (which the game calls an arena) for people to join. This smaller dictionary is used to store the information of the arena he has up.

def logfiller(): # logfiller() is a helper function used to load the data from the SQLite3 database into a Python list.
    conn = sqlite3.connect("playerlog")
    cursor = conn.cursor()
    #cursor.execute("CREATE TABLE players(twitchname text, switchname text, dateplayed date)")
    cursor.execute("DELETE FROM players WHERE dateplayed <= date('now', '-7 day')")
    cursor.execute("SELECT * FROM players")
    full_log = [(i[0], i[1]) for i in cursor.fetchall()]
    conn.commit()
    cursor.close()
    return full_log

full_log = logfiller()

def write_to_log(player): # After a player has completed their turn, their name will be recorded in the SQLite3 database.
    conn = sqlite3.connect("playerlog")
    cursor = conn.cursor()
    usertwitchname = player[0]
    userswitchname = player[1]
    userdateplayed = datetime.date.today().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO players(twitchname, switchname, dateplayed) values(:usertwitchname, :userswitchname, :userdateplayed)",{'usertwitchname': usertwitchname, 'userswitchname': userswitchname, 'userdateplayed': userdateplayed})
    cursor.execute("SELECT * FROM players")
    print(cursor.fetchall())
    conn.commit()
    cursor.close()
    with open('log.csv', 'a') as f: # The data is also stored in a csv file in case something goes wrong.
        f.write("{},{},{}\n".format(player[0], player[1], datetime.date.today().strftime("%Y-%m-%d")))

def backuplog(player, filename): # This function is used to store a player as backup in a csv file
    with open(filename, 'a') as f:
        f.write("{},{}\n".format(player[0], player[1]))

def intchecker(num): # A handful of commands used to alter data structures involve an optional position argument. intchecker() is used to determine whether or not a position was provided.
    try:
        newnum = int(num)
        return True
    except:
        return False

bot = commands.Bot(
    irc_token='', # Put oauth in
    client_id='', # Put client id in
    # The oauth and client ID are more sensitive information that I would rather not share publicly, but the above 2 lines shouldn't be empty strings.
    nick='ZardBot',
    prefix='!', # The prefix indicates what each command starts with. For instance, !join, !plug, etc.
    initial_channels=['IntroSpecktive', 'MacAtk_', 'RedFlare97'] # This indicates the Twitch channels that the bot will be active in when the program is run.
)

@bot.event
async def event_ready(): # This is the function that gets triggered when the bot starts up.
    print(f"ZardBot is sent out!")
    print(full_log) # I am printing the full_log in the terminal (not the Twitch chat) so I can verify that it is working.
    ws = bot._ws

@bot.event
async def event_message(ctx): # This function is to ensure that commands are handles properly independent of viewer messages. ctx is a parameter in many of the functions indicating the context, or the message that induced the command.
    await bot.handle_commands(ctx)

@bot.event
async def event_command_error(ctx, error): # This function is used to ignore errors, such as if a user types a command that doesn't exist.
    if isinstance(error, commands.CommandNotFound) or isinstance(error, commands.CommandError):
        pass

@bot.event
async def event_usernotice_subscription(ctx): # When a new user subscribes, they do have the option of new subscriber priority, which they can opt in.
    if toggles["open"]:
        if ctx.cumulative_months <= 1 and toggles['newsubperk']:
            if ("check !showsubs", "check !showsubs") not in playerqueue:
                playerqueue.insert(1, ("check !showsubs", "check !showsubs"))
            sublist.append((ctx.user.name.lower(), "NULL"))
            backuplog((ctx.user.name.lower(), "NULL"), "backupsublog.csv")
            await ctx.channel.send("@{} you get priority as a new sub. Type [!optin in_game_name] or !optout depending on if you want in or not (don't actually use the [ ])".format(ctx.user.name))
            print("Sub message sent")

@bot.command(name='toggle') # !toggle keyname is used by moderators to toggle on or off the various restrictions for the stream.
async def toggle(ctx):
    if ctx.author.is_mod:
        if ' ' not in ctx.content:
            await ctx.channel.send("@{} you forgot to give an argument for what is to be toggled.".format(ctx.author.name))
        else:
            if ctx.content.split(' ')[1].lower() not in toggles.keys():
                await ctx.channel.send("@{} {} is not a togglable argument. Current togglable arguments: {}".format(ctx.author.name, ctx.content.split()[1], toggles))
            else:
                toggles[ctx.content.split(' ')[1].lower()] = not toggles[ctx.content.split(' ')[1].lower()]
                await ctx.channel.send("@{} here are the states of your booleans: {}".format(ctx.author.name, toggles))

@bot.command(name='setid')
async def setid(ctx): # !setid ARENA_ID allows a moderator to alter the arena ID.
    if ctx.author.is_mod:
        temp = ctx.content.split(" ")
        if len(temp) < 2:
            await ctx.channel.send("@{} you need to provide an arena ID. Type !setid ARENA_ID".format(ctx.author.name))
        else:
            info['arenaid'] = temp[2]
            await ctx.channel.send("@{} the ID has been set to {}".format(ctx.author.name,info['arenaid']))

@bot.command(name='arena')
async def arena(ctx): # !arena prints the arena ID in the chat so that viewers can join.
    await ctx.channel.send("{}".format(info['arenaid']))

@bot.command(name='amifree')
async def amifree(ctx): # !amifree allows a user to check if they can play today.
    if toggles['variety']:
        if ctx.author.name.lower() in [i[0] for i in full_log]+[i[0] for i in played]:
            await ctx.channel.send("@{} you have played in the past week or just now. In either case, give others a chance pls.".format(ctx.author.name))
        else:
            await ctx.channel.send("@{} all clear! Go for it!!".format(ctx.author.name))
    else:
        if ctx.author.name.lower() in [i[0] for i in played]:
            await ctx.channel.send("@{} you have played today already. Give others a chance pls.".format(ctx.author.name))
        else:
            await ctx.channel.send("@{} all clear! Go for it!!".format(ctx.author.name))

@bot.command(name='optin')
async def optin(ctx): # !optin in_game_name is to be used by the new subscriber, but only intended if they were propmpted to do so from event_usernotice_subscription()
    if ctx.author.name.lower() in [i[0] for i in sublist]:
        if " " in ctx.content: # The user needs to provide their in game name so that the streamer can verify that it's actually them when they join his lobby.
            sublist[sublist.index((ctx.author.name.lower(), "NULL"))] = (ctx.author.name.lower(), ' '.join(ctx.content.split(" ")[1:]).lower())
            backuplog((ctx.author.name.lower(), ' '.join(ctx.content.split(" ")[1:]).lower()), "backupsublog.csv")
            await ctx.channel.send("@{} you've been registered in the new subs list! The arena ID is {}".format(ctx.author.name, info["arenaid"]))
        else:
            await ctx.channel.send("@{} you need to provide your in game name too! Type [!optin in_game_name]".format(ctx.author.name))
    else:
        await ctx.channel.send("@{} you're not on the new sub list rn.".format(ctx.author.name))

@bot.command(name='optout')
async def optout(ctx): # !optout is also intended for the user to opt out, but only if they were prompted to do so from event_usernotice_subscription().
    if ctx.author.name.lower() in [i[0] for i in sublist]:
        sublist.remove((ctx.author.name.lower(), "NULL"))
        await ctx.channel.send("@{} you've opted out of the new sub list.".format(ctx.author.name))
    else:
        await ctx.channel.send("@{} you're not on the new sub list rn.".format(ctx.author.name))

@bot.command(name='queue')
async def queue(ctx): # !queue prints the current state of the player list in chat.
    print(playerqueue)
    await ctx.channel.send("{}".format(playerqueue))

@bot.command(name='playedlist')
async def playedlist(ctx): # !playedlist prints the state of the current set of players who have played during the stream in chat.
    print(played)
    await ctx.channel.send("{}".format(played))

@bot.command(name='showsubs')
async def showsubs(ctx): # !showsubs prints the state of the subscriber list in chat.
    print(sublist)
    await ctx.channel.send("{}".format(sublist))

@bot.command(name='remove')
async def remove(ctx): # !remove player is a moderator command used to remove someone from playerqueue, as well as !sublist.
    if ctx.author.is_mod:
        if ' ' in ctx.content:
            userplayed = ' '.join(ctx.content.split(' ')[1:]).lower()
            if userplayed in [i[0] for i in playerqueue]+[i[1] for i in playerqueue]:
                for person in playerqueue:
                    if person[0] == userplayed or person[1] == userplayed:
                        playerqueue.remove(person)
                        played.add(person)
                        write_to_log(person)
                        if person in sublist:
                            sublist.remove(person)
                            if len(sublist) == 0 and playerqueue[1] == ("check !showsubs", "check !showsubs"):
                                playerqueue.remove(("check !showsubs", "check !showsubs"))
                        break

                await ctx.channel.send("{} has been removed from the queue.".format(userplayed))
            else:
                await ctx.channel.send("{} isn't in the queue.".format(userplayed))
        else:
            await ctx.channel.send("@{} who did you want to remove? Type [!remove userplayed] referring to their in game or Twitch name (w/o the [])".format(ctx.author.name))

@bot.command(name='clearqueue')
async def clearqueue(ctx): # If necessary, a moderator can clear the entire playerqueue and sublist.
    if ctx.author.is_mod:
        if ("check !showsubs", "check !showsubs") in playerqueue:
            sublist.clear()
        playerqueue.clear()
        await ctx.channel.send("@{} the player queue has been cleared".format(ctx.author.name))

@bot.command(name='removesub')
async def removesub(ctx): # !removesub player is a moderator only command to remove a subscriber from sublist specifically.
    if ctx.author.is_mod:
        if ' ' in ctx.content:
            userplayed = ' '.join(ctx.content.split(' ')[1:]).lower()
            if userplayed in [i[0] for i in sublist]+[i[1] for i in sublist]:
                for charmander in sublist:
                    if charmander[0] == userplayed or charmander[1] == userplayed:
                        sublist.remove(charmander)
                        break
                if len(sublist) == 0 and ("check !showsubs", "check !showsubs") in playerqueue:
                    playerqueue.remove(("check !showsubs", "check !showsubs"))
                await ctx.channel.send("{} has been removed from the sublist.".format(userplayed))
            else:
                await ctx.channel.send("{} isn't in the sublist.".format(userplayed))
        else:
            await ctx.channel.send("@{} who did you want to remove? Type [!removesub persontoremove] referring to their in game or Twitch name (w/o the [])".format(ctx.author.name))

@bot.command(name='clearsubs')
async def clearsubs(ctx): # !clearsubs is used to clear the subscriber list specifically.
    if ctx.author.is_mod:
        sublist.clear()
        if ("check !showsubs", "check !showsubs") in playerqueue:
            playerqueue.remove(("check !showsubs", "check !showsubs"))
        await ctx.channel.send("@{} the sub list has been cleared".format(ctx.author.name))

@bot.command(name='removeplayed')
async def removeplayed(ctx): # !removeplayed player is a moderator command that removes a player from the set of played players.
    if ctx.author.is_mod:
        if ' ' in ctx.content:
            userplayed = ' '.join(ctx.content.split(' ')[1:]).lower()
            if userplayed in [i[0] for i in played]+[i[1] for i in played]:
                for person in played:
                    if person[0] == userplayed or person[1] == userplayed:
                        played.discard(person)
                        break
                await ctx.channel.send("{} has been removed from the played list.".format(userplayed))
            else:
                await ctx.channel.send("{} isn't in the played list.".format(userplayed))
        else:
            await ctx.channel.send("@{} who did you want to remove? Type [!removeplayed user] referring to their in game or Twitch name (w/o the [])".format(ctx.author.name))

@bot.command(name='clearplayed')
async def clearplayed(ctx): # clearplayed is a moderator command to clear the set of played players.
    if ctx.author.is_mod:
        played.clear()
        await ctx.channel.send("@{} the played list has been cleared".format(ctx.author.name))

@bot.command(name='pluglog')
async def pluglog(ctx): # !pluglog twitchname switchname is a command used to insert a player into the full_log()
    if ctx.author.is_mod:
        if ' ' in ctx.content:
            templist = ctx.content.split(' ')
            if templist[1].lower() in [i[0] for i in full_log]:
                await ctx.channel.send("{} is already in the full log".format(templist[1]))
            elif len(templist) < 3:
                await ctx.channel.send("@{} not enough positional arguments. It's [!pluglog twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))
            elif not intchecker(templist[-1]):
                full_log.append((templist[1].lower(), ' '.join(templist[2:]).lower()))
                write_to_log(full_log[-1])
                await ctx.channel.send("{} has been added to the full log at the back".format(playerqueue[-1][1]))
            else:
                full_log.insert(int(templist[-1]), (templist[1].lower(), ' '.join(templist[2:-1]).lower()))
                await ctx.channel.send("{} has been added to the full log at position {}".format(' '.join(templist[2:-1]).lower(),templist[-1]))
        else:
            await ctx.channel.send("@{} not enough positional arguments. It's [!pluglog twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))

@bot.command(name='removelog')
async def removelog(ctx): # !removelog player is used to remove a person from the full_log as well as the SQLite3 database.
    if ctx.author.is_mod:
        if ' ' in ctx.content:
            person = ' '.join(ctx.content.split(' ')[1:]).lower()
            if person in [i[0] for i in full_log]+[i[1] for i in full_log]:
                for player in full_log:
                    if person == player[0] or person == player[1]:
                        conn = sqlite3.connect("playerlog")
                        cursor = conn.cursor()
                        if person == player[0]:
                            cursor.execute("DELETE FROM players WHERE twitchname = '{}'".format(person))
                        elif person == player[1]:
                            cursor.execute("DELETE FROM players WHERE switchname = '{}'".format(person))
                        cursor.execute("SELECT * FROM players")
                        print(cursor.fetchall()) # Printing the contents of the database to the terminal just to double check
                        conn.commit()
                        cursor.close()
                        full_log.remove(player)
                        break
                await ctx.channel.send("{} has been removed from the full log".format(person))
            else:
                await ctx.channel.send("{} isn't in the full log".format(person))
        else:
            await ctx.channel.send("@{} not enough positional arguments. It's [!removelog twitchname] or [!removelog switchname] without the [ ]".format(ctx.author.name))
'''
@bot.command(name='clearlog')
async def clearlog(ctx):
    if ctx.author.is_mod:
        conn = sqlite3.connect("playerlog")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM players")
        cursor.execute("SELECT * FROM players")
        print(cursor.fetchall())
        conn.commit()
        cursor.close()
        full_log.clear()
        await ctx.channel.send("@{} the full log has been cleared".format(ctx.author.name))
'''
@bot.command(name='showlog')
async def showlog(ctx): # !showlog is a moderator only command that prints the database contents to the terminal, usually only intended for the moderator running the program.
    if ctx.author.is_mod:
        print(full_log)
        conn = sqlite3.connect("playerlog")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players")
        print(cursor.fetchall())
        conn.commit()
        cursor.close()

@bot.command(name='next')
async def next(ctx): # !next is the command intended for the streamer to use once they're finished with a person. This takes into account subscriber priority as well.
    if ctx.author.is_mod:
        if len(playerqueue) > 0:
            if playerqueue[0] != ("check !showsubs", "check !showsubs"):
                removed = playerqueue.pop(0)
                played.add(removed)
                write_to_log(removed)
                if len(playerqueue) > 0:
                    if playerqueue[0] != ("check !showsubs", "check !showsubs"):
                        await ctx.channel.send("{} is done. {} is up next! @{} the arena info is in !arena, so pls join the room".format(removed[1], playerqueue[0][1], playerqueue[0][0]))
                    else:
                        await ctx.channel.send("{} is done. {} is up next! @{} the arena info is in !arena, so pls join the room".format(removed[1], sublist[0][1], sublist[0][0]))
                else:
                    await ctx.channel.send("{} is done. No one else in line!".format(removed[1]))
            else:
                removed = sublist.pop(0)
                played.add(removed)
                write_to_log(removed)
                if len(sublist) == 0:
                    playerqueue.pop(0)
                    if len(playerqueue) > 0:
                        await ctx.channel.send("{} is done. {} is up next! @{} the arena info is in !arena, so pls join the room".format(removed[1], playerqueue[0][1], playerqueue[0][0]))
                    else:
                        await ctx.channel.send("{} is done. No one else in line!".format(removed[1]))
                else:
                    await ctx.channel.send("{} is done. {} is up next! @{} the arena info is in !arena, so pls join the room".format(removed[1], sublist[0][1], sublist[0][0]))
        else:
            await ctx.channel.send("No one's in line!")

@bot.command(name='join')
async def join(ctx): # !join ingamename is the command for users to join the list.
    if not toggles['open']:
        await ctx.channel.send("@{} the list is closed atm. Sorry!".format(ctx.author.name))
    elif ctx.author.name.lower() in [i[0] for i in played] or (toggles['variety'] and ctx.author.name.lower() in [i[0] for i in full_log]):
        await ctx.channel.send("@{} you already played today. Sorry!".format(ctx.author.name))
    elif toggles['subsonlymode'] and not ctx.author.is_subscriber:
        if toggles['verbose']:
            await ctx.channel.send("@{} the list is subs only rn. Sorry!".format(ctx.author.name))
        else:
            print("No verbose lol")
    elif toggles['limit'] and len(playerqueue) >= 7:
        if toggles['verbose']:
            await ctx.channel.send("@{} The list is full. Try joining when Intro hits !next".format(ctx.author.name))
        else:
            print("No verbose lol")
    elif ctx.author.name.lower() in [i[0] for i in playerqueue]:
        await ctx.channel.send("@{} you're already in the queue".format(ctx.author.name))
    else:
        if ' ' in ctx.content:
            playerqueue.append((ctx.author.name.lower(), ' '.join(ctx.content.split(' ')[1:]).lower()))
            backuplog(playerqueue[-1], "backuplog.csv")
            await ctx.channel.send("@{} I've added you to the list! Your in game name is {}".format(ctx.author.name, ' '.join(ctx.content.split(' ')[1:]).lower()))
        else:
            await ctx.channel.send("@{} you didn't provide enough arguments! It's [!join in_game_name] without the [ ]".format(ctx.author.name))

@bot.command(name='drop')
async def drop(ctx): # If a user can no longer play, they can type !drop to remove themselves from the list.
    if ctx.author.name.lower() in [i[0] for i in playerqueue]:
        for person in playerqueue:
            if person[0] == ctx.author.name.lower():
                playerqueue.remove(person)
                await ctx.channel.send("@{} you have dropped from the list".format(ctx.author.name))
                break
    else:
        await ctx.channel.send("@{} you aren't in the list".format(ctx.author.name))

@bot.command(name='changename')
async def changename(ctx): # If a user input their name wrong when joining, a moderator can use !changename twitchname newingamename to fix the mishap.
    if ctx.author.is_mod:
        templist = ctx.content.split(' ')
        if templist[1].lower() in [i[0] for i in playerqueue]:
            if len(templist) < 3:
                await ctx.channel.send("@{} not enough positional arguments. It's !changename twitchname newingamename".format(ctx.author.name))
            else:
                for person in playerqueue:
                    if person[0] == templist[1].lower():
                        playerqueue[playerqueue.index(person)] = (templist[1].lower(), ' '.join(templist[2:]).lower())
                        await ctx.channel.send("@{} I've changed @{}'s in game name to {}".format(ctx.author.name, templist[1].lower(), ' '.join(templist[2:]).lower()))
                        break
        else:
            await ctx.channel.send("@{} I couldn't find this user in the queue".format(ctx.author.name))

@bot.command(name='plug')
async def plug(ctx): # !plug twitchname switchname is a moderator only command to insert someone into the list.
    if ctx.author.is_mod:
        if ' ' in ctx.content:
            templist = ctx.content.split(' ')
            if templist[1].lower() in [i[0] for i in playerqueue]:
                await ctx.channel.send("{} is already in the queue".format(templist[1]))
            elif len(templist) < 3:
                await ctx.channel.send("@{} not enough positional arguments. It's [!plug twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))
            elif not intchecker(templist[-1]):
                playerqueue.append((templist[1].lower(), ' '.join(templist[2:]).lower()))
                backuplog(playerqueue[-1], "backuplog.csv")
                if playerqueue[-1] in played:
                    played.discard(playerqueue[-1])
                await ctx.channel.send("{} has been added to the queue at the back".format(playerqueue[-1][1]))
            else:
                playerqueue.insert(int(templist[-1]), (templist[1].lower(), ' '.join(templist[2:-1]).lower()))
                if (templist[1].lower(), ' '.join(templist[2:-1]).lower()) in played:
                    played.discard((templist[1].lower(), ' '.join(templist[2:-1]).lower()))
                await ctx.channel.send("{} has been added to the queue at position {}".format(' '.join(templist[2:-1]).lower(), templist[-1]))
        else:
            await ctx.channel.send("@{} not enough positional arguments. It's [!plug twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))

@bot.command(name='plugsub')
async def plugsub(ctx):
    if ctx.author.is_mod: # !plugsub twitchname switchname is a moderator only command used to plug someone into the sublist.
        if ("check !showsubs", "check !showsubs") not in playerqueue:
            playerqueue.insert(1, ("check !showsubs", "check !showsubs"))
        if ' ' in ctx.content:
            templist = ctx.content.split(' ')
            if templist[1].lower() in [i[0] for i in sublist]:
                await ctx.channel.send("{} is already in the queue".format(templist[1]))
            elif len(templist) < 3:
                await ctx.channel.send("@{} not enough positional arguments. It's [!plugsub twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))
            elif not intchecker(templist[-1]):
                sublist.append((templist[1].lower(), ' '.join(templist[2:]).lower()))
                backuplog(sublist[-1], "backupsublog.csv")
                if sublist[-1] in played:
                    played.discard(sublist[-1])
                await ctx.channel.send("{} has been added to the sublist at the back".format(sublist[-1][1]))
            else:
                sublist.insert(int(templist[-1]), (templist[1].lower(), ' '.join(templist[2:-1]).lower()))
                if (templist[1].lower(), ' '.join(templist[2:-1]).lower()) in played:
                    played.discard((templist[1].lower(), ' '.join(templist[2:-1]).lower()))
                await ctx.channel.send("{} has been added to the sublist at position {}".format(' '.join(templist[2:-1]).lower(), templist[-1]))
        else:
            await ctx.channel.send("@{} not enough positional arguments. It's [!plugsub twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))

@bot.command(name='plugplayed')
async def plugplayed(ctx): # !plugplayed switchname twitchname is a moderator only command to add a user to the set of players who already played.
    if ctx.author.is_mod:
        if ' ' in ctx.content:
            templist = ctx.content.split(' ')
            if templist[1].lower() in [i[0] for i in played]:
                await ctx.channel.send("{} is already in the played list".format(templist[1]))
            elif len(templist) < 3:
                await ctx.channel.send("@{} not enough positional arguments. It's [!plugplayed switchname twitchname] without the [ ]. If no information is provided on Twitch name, just type twitchless in place for it".format(ctx.author.name))
            else:
                played.add((templist[1].lower(), ' '.join(templist[2:]).lower()))
                await ctx.channel.send("{} has been added to the played list".format(templist[1].lower()))
        else:
            await ctx.channel.send("@{} not enough positional arguments. It's [!plugplayed switchname twitchname] without the [ ]. If no information is provided on Twitch name, just type twitchless for twitchname".format(ctx.author.name))

@bot.command(name='fillqueue')
async def fillqueue(ctx): # In the event the program needs to be rerun, the data can be immediately loaded from backuplog.csv, which is updated alongside the list.
    if ctx.author.is_mod:
        with open("backuplog.csv", 'r') as f:
            for person in f.read().split('\n'):
                if ',' in person:
                    playerqueue.append((person.split(',')[0],person.split(',')[1]))
                    backuplog(playerqueue[-1], "backuplog.csv")
        await ctx.channel.send("@{} the queue has been restored".format(ctx.author.name))

@bot.command(name='fillsubs')
async def fillsubs(ctx): # Similarly to the above command, !fillsubs is used to restore the sublist.
    if ctx.author.is_mod:
        with open("backupsublog.csv", 'r') as f:
            for person in f.read().split('\n'):
                if ',' in person:
                    playerqueue.append((person.split(',')[0],person.split(',')[1]))
                    backuplog(playerqueue[-1], "backupsublog.csv")
        await ctx.channel.send("@{} the subs list has been restored".format(ctx.author.name))

if __name__ == "__main__": # When the program runs, the terminal will print an error, something along the lines of "channel not found". Ignore that. As long as the commands work in the chat, it should be fine.
    bot.run()
