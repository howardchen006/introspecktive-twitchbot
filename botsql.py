import asyncio
import sqlite3
import hivemindsecrets

from twitchio import Channel
from twitchio.ext import commands
import datetime
import numpy as np

"""
This bot is designed to manage viewer battles for the game Super Smash Bros. Ultimate, which IntroSpecktive plays on stream.
During viewer battles, viewers in the stream register themselves to a line automated by this application, so that
IntroSpecktive can play people in an orderly fashion.
"""


"""
self.toggles is a dictionary of booleans that is used to enforce restrictions on the queue depending on the streamer's ideals.
"newsubperk" is an on switch for the automation of a new subscriber being offered a spot on the queue upon their subscription.
"subsonlymode" being True restricts the queue to subscribers only when IntroSpecktive feels like playing subscribers only on certain days.
"limit" being True restricts the cardinality of the queue to 7 at a time so it doesn't get too large, which can detract viewers.
"open" dictates whether the queue is open for joining at a given point in time.
"verbose" was implemented so that selective bot messages can be muted in case viewers spam the bot commands.
"variety" being True means that players who have played within the past week (determined by data within a SQLite3 database) are inhibited from joining, so that different people get a chance to play.
"""
info = {'arenaid': None} # In the game Super Smash Bros. Ultimate, IntroSpecktive creates a lobby (which the game calls an arena) for people to join. This smaller dictionary is used to store the information of the arena he has up.

twitchnames = np.vectorize(lambda player: player.split("🔥")[0],otypes=[str])
switchnames = np.vectorize(lambda player: player.split("🔥")[1],otypes=[str])
def logfiller(): # logfiller() is a helper function used to load the data from the SQLite3 database into a Python list.
    conn = sqlite3.connect("playerlog")
    cursor = conn.cursor()
    #cursor.execute("CREATE TABLE players(twitchname text, switchname text, dateplayed date)")
    cursor.execute("DELETE FROM players WHERE dateplayed <= date('now', '-7 day')")
    cursor.execute("SELECT * FROM players")
    full_log = np.array(["{}🔥{}".format(i[0],i[1]) for i in cursor.fetchall()])
    conn.commit()
    cursor.close()
    return full_log

full_log = logfiller()

def write_to_log(player): # After a player has completed their turn, their name will be recorded in the SQLite3 database.
    conn = sqlite3.connect("playerlog")
    cursor = conn.cursor()
    usertwitchname = player.split("🔥")[0]
    userswitchname = player.split("🔥")[1]
    userdateplayed = datetime.date.today().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO players(twitchname, switchname, dateplayed) values(:usertwitchname, :userswitchname, :userdateplayed)",{'usertwitchname': usertwitchname, 'userswitchname': userswitchname, 'userdateplayed': userdateplayed})
    cursor.execute("SELECT * FROM players")
    print(cursor.fetchall())
    conn.commit()
    cursor.close()
    with open('log.csv', 'a') as f: # The data is also stored in a csv file in case something goes wrong.
        f.write("{},{},{}\n".format(usertwitchname, userswitchname, datetime.date.today().strftime("%Y-%m-%d")))

def backuplog(playerqueue, filename): # This function is used to store a player as backup in a csv file
    with open(filename, 'w') as f:
        f.write("\n".join([player.replace("🔥",",") for player in playerqueue]))

def intchecker(num): # A handful of commands used to alter data structures involve an optional position argument. intchecker() is used to determine whether or not a position was provided.
    try:
        newnum = int(num)
        return True
    except:
        return False

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=hivemindsecrets.token,  # Put oauth in
            client_id=hivemindsecrets.client_id,  # Put client id in
            client_secret=hivemindsecrets.client_secret,  # Put client secret in
            # The above variables are more sensitive information that I would rather not share publicly, but the above lines shouldn't be empty strings.
            nick='ZardBot',
            prefix='!', # The prefix indicates what each command starts with. For instance, !join, !plug, etc.
            initial_channels=['IntroSpecktive', 'MacAtk_', 'RedFlare006'] # This indicates the Twitch channels that the bot will be active in when the program is run.
        )
        self.next_cd = None
        self.playerqueue = np.array([])  # Stores the current list of people in the line.
        self.sublist = np.array([])  # On Twitch, channels have both regular viewers and subscribers, the latter being a paid subscription.
        # As a way to give back to the subscribers, IntroSpecktive likes to give subscribers priority, hence a separate list for them.
        self.played = set()  # Once people have finished their turn, their name will be stored in this set to inhibit them from
        # rejoining the queue so that more people have a chance to play.
        self.toggles = {'newsubperk': True, 'subsonlymode': False, 'limit': True, 'open': False, 'verbose': True,
                   'variety': False, 'runback': False}

    async def cooldown(self):
        print("nextn't")
        await asyncio.sleep(10)
        print("next")
        return

    async def event_ready(self,): # This is the function that gets triggered when the bot starts up.
        print(f"ZardBot is sent out!")
        print(full_log) # I am printing the full_log in the terminal (not the Twitch chat) so I can verify that it is working.

    async def event_message(self,ctx): # This function is to ensure that commands are handles properly independent of viewer messages. ctx is a parameter in many of the functions indicating the context, or the message that induced the command.
        await bot.handle_commands(ctx)

    async def event_command_error(self,ctx,error): # This function is used to ignore errors, such as if a user types a command that doesn't exist.
        print(error)

    async def event_raw_usernotice(self,channel,tags):
        print(tags)
        if tags["msg-id"] in ["subgift","sub"] and self.toggles["open"] and self.toggles["newsubperk"]:
            if tags["msg-id"]=="subgift":
                newsub = tags['msg-param-recipient-display-name']
            else:
                newsub = tags['display-name']
            if "check !showsubs🔥check !showsubs" not in self.playerqueue:
                self.playerqueue = np.insert(self.playerqueue, 1, "check !showsubs🔥check !showsubs")
            self.sublist = np.append(self.sublist, np.array(["{}🔥NULL".format(newsub.lower())]))
            backuplog(self.sublist, "backupsublog.csv")
            await channel.send("@{} you get priority as a new sub. Type [!optin in_game_name] or !optout depending on if you want in or not (don't actually use the [ ])".format(newsub))
            print("Sub message sent")
    """
    async def event_usernotice_subscription(self,ctx): # When a new user subscribes, they do have the option of new subscriber priority, which they can opt in.
        print("New sub")
        if self.toggles["open"]:
            print("NEW SUB HYPE")
            if ctx.cumulative_months <= 1 and self.toggles['newsubperk']:
                if "check !showsubs🔥check !showsubs" not in self.playerqueue:
                    self.playerqueue = np.insert(self.playerqueue,1,"check !showsubs🔥check !showsubs")
                self.sublist = np.append(self.sublist,np.array(["{}🔥NULL".format(ctx.user.name.lower())]))
                backuplog(self.sublist, "backupsublog.csv")
                await ctx.channel.send("@{} you get priority as a new sub. Type [!optin in_game_name] or !optout depending on if you want in or not (don't actually use the [ ])".format(ctx.user.name))
                print("Sub message sent")
    """
    @commands.command(name='toggle') # !toggle keyname is used by moderators to toggle on or off the various restrictions for the stream.
    async def toggle(self,ctx):
        if ctx.author.is_mod:
            if ' ' not in ctx.message.content:
                await ctx.channel.send("@{} you forgot to give an argument for what is to be toggled.".format(ctx.author.name))
            else:
                if ctx.message.content.split(' ')[1].lower() not in self.toggles.keys():
                    await ctx.channel.send("@{} {} is not a togglable argument. Current togglable arguments: {}".format(ctx.author.name, ctx.message.content.split()[1], self.toggles))
                else:
                    self.toggles[ctx.message.content.split(' ')[1].lower()] = not self.toggles[ctx.message.content.split(' ')[1].lower()]
                    await ctx.channel.send("@{} here are the states of your booleans: {}".format(ctx.author.name, self.toggles))

    @commands.command(name='setid')
    async def setid(self,ctx): # !setid ARENA_ID allows a moderator to alter the arena ID.
        if ctx.author.is_mod:
            temp = ctx.message.content.split(" ")
            if len(temp) < 2:
                await ctx.channel.send("@{} you need to provide an arena ID. Type !setid ARENA_ID".format(ctx.author.name))
            else:
                info['arenaid'] = temp[1]
                await ctx.channel.send("@{} the ID has been set to {}".format(ctx.author.name,info['arenaid']))

    @commands.command(name='arena')
    async def arena(self,ctx): # !arena prints the arena ID in the chat so that viewers can join.
        await ctx.channel.send("{}".format(info['arenaid']))

    @commands.command(name='amiasub')
    async def amiasub(self,ctx):
        await ctx.channel.send("{}".format(ctx.author.is_subscriber))

    @commands.command(name='amifree')
    async def amifree(self,ctx): # !amifree allows a user to check if they can play today.
        if self.toggles['variety']:
            if ctx.author.name.lower() in twitchnames(full_log) or ctx.author.name.lower() in self.played:
                await ctx.channel.send("@{} you have played in the past week or just now. In either case, give others a chance pls.".format(ctx.author.name))
            else:
                await ctx.channel.send("@{} all clear! Go for it!!".format(ctx.author.name))
        else:
            if ctx.author.name.lower() in self.played:
                await ctx.channel.send("@{} you have played today already. Give others a chance pls.".format(ctx.author.name))
            else:
                await ctx.channel.send("@{} all clear! Go for it!!".format(ctx.author.name))

    @commands.command(name='optin')
    async def optin(self,ctx): # !optin in_game_name is to be used by the new subscriber, but only intended if they were propmpted to do so from event_usernotice_subscription()
        if ctx.author.name.lower() in twitchnames(self.sublist):
            if " " in ctx.message.content: # The user needs to provide their in game name so that the streamer can verify that it's actually them when they join his lobby.
                self.sublist[np.where(twitchnames(self.sublist)==ctx.author.name.lower())] = ctx.author.name.lower()+"🔥"+' '.join(ctx.message.content.split(" ")[1:]).lower()
                backuplog(self.sublist, "backupsublog.csv")
                await ctx.channel.send("@{} you've been registered in the new subs list! The arena ID is {}".format(ctx.author.name, info["arenaid"]))
            else:
                await ctx.channel.send("@{} you need to provide your in game name too! Type [!optin in_game_name]".format(ctx.author.name))
        else:
            await ctx.channel.send("@{} you're not on the new sub list rn.".format(ctx.author.name))

    @commands.command(name='optout')
    async def optout(self,ctx): # !optout is also intended for the user to opt out, but only if they were prompted to do so from event_usernotice_subscription().
        if ctx.author.name.lower() in twitchnames(self.sublist):
            self.sublist = np.delete(self.sublist,np.where(twitchnames(self.sublist)==ctx.author.name.lower()))
            if self.sublist.shape[0] == 0:
                self.playerqueue = np.delete(self.playerqueue,np.where(self.playerqueue=="check !showsubs🔥check !showsubs"))
            await ctx.channel.send("@{} you've opted out of the new sub list.".format(ctx.author.name))
        else:
            await ctx.channel.send("@{} you're not on the new sub list rn.".format(ctx.author.name))

    @commands.command(name='queue')
    async def queue(self,ctx): # !queue prints the current state of the player list in chat.
        print(self.playerqueue)
        await ctx.channel.send("{}".format(self.playerqueue))

    @commands.command(name='playedlist')
    async def playedlist(self,ctx): # !playedlist prints the state of the current set of players who have played during the stream in chat.
        print(self.played)
        await ctx.channel.send("{}".format(self.played))

    @commands.command(name='showsubs')
    async def showsubs(self,ctx): # !showsubs prints the state of the subscriber list in chat.
        print(self.sublist)
        await ctx.channel.send("{}".format(self.sublist))

    @commands.command(name='remove')
    async def remove(self,ctx): # !remove player is a moderator command used to remove someone from playerqueue, as well as sublist.
        if ctx.author.is_mod:
            if ' ' in ctx.message.content:
                userplayed = ' '.join(ctx.message.content.split(' ')[1:]).lower()
                if userplayed in np.append(twitchnames(self.playerqueue),switchnames(self.playerqueue)):
                    ind = np.where(twitchnames(self.playerqueue)==userplayed)
                    if len(ind[0])==0:
                        ind = np.where(switchnames(self.playerqueue)==userplayed)
                    person = twitchnames(self.playerqueue)[ind][0]
                    #self.played.add(person)
                    #write_to_log(self.playerqueue[ind])
                    self.playerqueue = np.delete(self.playerqueue,ind)
                    await ctx.channel.send("{} has been removed from the queue.".format(person))
                else:
                    await ctx.channel.send("{} isn't in the queue.".format(userplayed))
            else:
                await ctx.channel.send("@{} who did you want to remove? Type [!remove userplayed] referring to their in game or Twitch name (w/o the [])".format(ctx.author.name))

    @commands.command(name='clearqueue')
    async def clearqueue(self,ctx): # If necessary, a moderator can clear the entire self.playerqueue and self.sublist.
        if ctx.author.is_mod:
            if "check !showsubs🔥check !showsubs" in self.playerqueue:
                self.sublist = np.array([])
            self.playerqueue = np.array([])
            await ctx.channel.send("@{} the player queue has been cleared".format(ctx.author.name))

    @commands.command(name='removesub')
    async def removesub(self,ctx): # !removesub player is a moderator only command to remove a subscriber from self.sublist specifically.
        if ctx.author.is_mod:
            if ' ' in ctx.message.content:
                userplayed = ' '.join(ctx.message.content.split(' ')[1:]).lower()
                if userplayed in np.append(twitchnames(self.sublist),switchnames(self.sublist)):
                    ind = np.where(twitchnames(self.sublist) == userplayed)
                    if len(ind[0]) == 0:
                        ind = np.where(switchnames(self.sublist) == userplayed)
                    self.sublist = np.delete(self.sublist, ind)
                    if len(self.sublist) == 0 and self.playerqueue[1] == "check !showsubs🔥check !showsubs":
                        self.playerqueue = np.delete(self.playerqueue, 1)
                    await ctx.channel.send("{} has been removed from the sublist.".format(userplayed))
                else:
                    await ctx.channel.send("{} isn't in the sublist.".format(userplayed))
            else:
                await ctx.channel.send("@{} who did you want to remove? Type [!removesub persontoremove] referring to their in game or Twitch name (w/o the [])".format(ctx.author.name))

    @commands.command(name='clearsubs')
    async def clearsubs(self,ctx): # !clearsubs is used to clear the subscriber list specifically.
        if ctx.author.is_mod:
            self.sublist = np.array([])
            if "check !showsubs🔥check !showsubs" in self.playerqueue:
                self.playerqueue = np.delete(self.playerqueue,np.where(twitchnames(self.playerqueue)=="check !showsubs"))
            await ctx.channel.send("@{} the sub list has been cleared".format(ctx.author.name))

    @commands.command(name='removeplayed')
    async def removeplayed(self,ctx): # !removeplayed player is a moderator command that removes a player from the set of played players.
        if ctx.author.is_mod:
            if ' ' in ctx.message.content:
                userplayed = ' '.join(ctx.message.content.split(' ')[1]).lower()
                if userplayed in self.played:
                    self.played.remove(userplayed)
                    await ctx.channel.send("{} has been removed from the played list.".format(userplayed))
                else:
                    await ctx.channel.send("{} isn't in the played list.".format(userself.played))
            else:
                await ctx.channel.send("@{} who did you want to remove? Type [!removeplayed user] referring to their in game or Twitch name (w/o the [])".format(ctx.author.name))

    @commands.command(name='clearplayed')
    async def clearplayed(self,ctx): # clearplayed is a moderator command to clear the set of played players.
        if ctx.author.is_mod:
            self.played.clear()
            await ctx.channel.send("@{} the played list has been cleared".format(ctx.author.name))

    @commands.command(name='pluglog')
    async def pluglog(self,ctx): # !pluglog twitchname switchname is a command used to insert a player into the full_log()
        if ctx.author.is_mod:
            if ' ' in ctx.message.content:
                templist = ctx.message.content.split(' ')
                if templist[1].lower() in twitchnames(full_log):
                    await ctx.channel.send("{} is already in the full log".format(templist[1]))
                elif len(templist) < 3:
                    await ctx.channel.send("@{} not enough positional arguments. It's [!pluglog twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))
                elif not intchecker(templist[-1]):
                    full_log = np.append(full_log,np.array([templist[1].lower()+"🔥"+' '.join(templist[2:]).lower()]))
                    write_to_log(full_log[-1])
                    await ctx.channel.send("{} has been added to the full log at the back".format(full_log[-1]))
                else:
                    full_log = np.insert(full_log,int(templist[-1]), templist[1].lower()+"🔥"+' '.join(templist[2:-1]).lower())
                    await ctx.channel.send("{} has been added to the full log at position {}".format(' '.join(templist[2:-1]).lower(),templist[-1]))
            else:
                await ctx.channel.send("@{} not enough positional arguments. It's [!pluglog twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))

    @commands.command(name='removelog')
    async def removelog(self,ctx): # !removelog player is used to remove a person from the full_log as well as the SQLite3 database.
        if ctx.author.is_mod:
            if ' ' in ctx.message.content:
                person = ' '.join(ctx.message.content.split(' ')[1:]).lower()
                if person in np.append(twitchnames(full_log),switchnames(full_log)):
                    ind = np.where(twitchnames(full_log)==person)
                    flag = True
                    if len(ind[0]) == 0:
                        ind = np.where(switchnames(full_log)==person)
                        flag = False
                    conn = sqlite3.connect("playerlog")
                    cursor = conn.cursor()
                    if flag:
                        cursor.execute("DELETE FROM players WHERE twitchname = '{}'".format(person))
                    else:
                        cursor.execute("DELETE FROM players WHERE switchname = '{}'".format(person))
                    cursor.execute("SELECT * FROM players")
                    print(cursor.fetchall())  # Printing the contents of the database to the terminal just to double check
                    conn.commit()
                    cursor.close()
                    full_log = np.delete(full_log,ind)
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
    @commands.command(name='showlog')
    async def showlog(self,ctx): # !showlog is a moderator only command that prints the database contents to the terminal, usually only intended for the moderator running the program.
        if ctx.author.is_mod:
            print(full_log)
            conn = sqlite3.connect("playerlog")
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM players")
            print(cursor.fetchall())
            conn.commit()
            cursor.close()

    @commands.command(name='next')
    async def next(self,ctx): # !next is the command intended for the streamer to use once they're finished with a person. This takes into account subscriber priority as well.
        if (self.next_cd==None or self.next_cd.done()) and ctx.author.is_mod:
            if len(self.playerqueue) > 0:
                if self.playerqueue[0] != "check !showsubs🔥check !showsubs":
                    removed = self.playerqueue[0]
                    self.playerqueue = self.playerqueue[1:]
                    self.played.add(removed.split("🔥")[0])
                    write_to_log(removed)
                    if len(self.playerqueue) > 0:
                        if self.playerqueue[0] != "check !showsubs🔥check !showsubs":
                            await ctx.channel.send("{} is done. {} is up next! The arena info is in !arena, so pls join the room".format(removed, self.playerqueue[0]))
                        else:
                            await ctx.channel.send("{} is done. {} is up next! The arena info is in !arena, so pls join the room".format(removed, self.sublist[0]))
                    else:
                        await ctx.channel.send("{} is done. No one else in line!".format(removed))
                else:
                    removed = self.sublist[0]
                    self.sublist = self.sublist[1:]
                    self.played.add(removed.split("🔥")[0])
                    write_to_log(removed)
                    if len(self.sublist) == 0:
                        self.playerqueue = self.playerqueue[1:]
                        if len(self.playerqueue) > 0:
                            await ctx.channel.send("{} is done. {} is up next! The arena info is in !arena, so pls join the room".format(removed, self.playerqueue[0]))
                        else:
                            await ctx.channel.send("{} is done. No one else in line!".format(removed))
                    else:
                        await ctx.channel.send("{} is done. {} is up next! The arena info is in !arena, so pls join the room".format(removed, self.sublist[0]))
                backuplog(self.playerqueue, "backuplog.csv")
            else:
                await ctx.channel.send("No one's in line!")
            self.next_cd = asyncio.create_task(self.cooldown())

    @commands.command(name='join')
    async def join(self,ctx): # !join ingamename is the command for users to join the queue.
        if not self.toggles['open']:
            await ctx.channel.send("@{} the queue is closed atm. Sorry!".format(ctx.author.name))
        elif self.toggles['variety'] and ctx.author.name.lower() in twitchnames(full_log):
            await ctx.channel.send("@{} you already played recently. Sorry!".format(ctx.author.name))
        elif not self.toggles['runback'] and ctx.author.name.lower() in self.played:
            await ctx.channel.send("@{} you already played today. Sorry!".format(ctx.author.name))
        elif self.toggles['subsonlymode'] and not ctx.author.is_subscriber:
            if self.toggles['verbose']:
                await ctx.channel.send("@{} the queue is subs only rn. Sorry!".format(ctx.author.name))
            else:
                print("No verbose lol")
        elif self.toggles['limit'] and len(self.playerqueue) >= 7:
            if self.toggles['verbose']:
                await ctx.channel.send("@{} The queue is full. Try joining when Intro hits !next".format(ctx.author.name))
            else:
                print("No verbose lol")
        elif ctx.author.name.lower() in twitchnames(self.playerqueue):
            await ctx.channel.send("@{} you're already in the queue".format(ctx.author.name))
        else:
            if ' ' in ctx.message.content:
                self.playerqueue = np.append(self.playerqueue,ctx.author.name.lower()+"🔥"+' '.join(ctx.message.content.split(' ')[1:]).lower())
                backuplog(self.playerqueue, "backuplog.csv")
                await ctx.channel.send("@{} I've added you to the queue! Your in game name is {}".format(ctx.author.name, ' '.join(ctx.message.content.split(' ')[1:]).lower()))
            else:
                await ctx.channel.send("@{} you didn't provide enough arguments! It's [!join in_game_name] without the [ ]".format(ctx.author.name))

    @commands.command(name='drop')
    async def drop(self,ctx): # If a user can no longer play, they can type !drop to remove themselves from the queue.
        if ctx.author.name.lower() in twitchnames(self.playerqueue):
            self.playerqueue = np.delete(self.playerqueue,np.where(twitchnames(self.playerqueue)==ctx.author.name.lower()))
            await ctx.channel.send("@{} you have dropped from the queue".format(ctx.author.name))
            backuplog(self.playerqueue, "backuplog.csv")
        elif ctx.author.name.lower() in twitchnames(self.sublist):
            self.sublist = np.delete(self.sublist,np.where(twitchnames(self.sublist)==ctx.author.name.lower()))
            await ctx.channel.send("@{} you have dropped from the queue".format(ctx.author.name))
            backuplog(self.playerqueue, "backupsublog.csv")
        else:
            await ctx.channel.send("@{} you aren't in the queue".format(ctx.author.name))

    @commands.command(name='rename')
    async def rename(self,ctx):  # If a user input their name wrong when joining, they can use !changename newingamename to fix the mishap.
            if ctx.author.name.lower() in twitchnames(self.playerqueue):
                templist = ctx.message.content.split(' ')
                if len(templist) < 2:
                    await ctx.channel.send("@{} not enough positional arguments. It's !rename newingamename".format(ctx.author.name))
                else:
                    self.playerqueue[np.where(twitchnames(self.playerqueue)==ctx.author.name.lower())] = ctx.author.name.lower()+"🔥"+' '.join(templist[1:]).lower()
                    await ctx.channel.send("@{} I've changed your in game name to {}".format(ctx.author.name,' '.join(templist[1:]).lower()))
                    backuplog(self.playerqueue, "backuplog.csv")
            elif ctx.author.name.lower() in twitchnames(self.sublist):
                templist = ctx.message.content.split(' ')
                if len(templist) < 2:
                    await ctx.channel.send("@{} not enough positional arguments. It's !rename newingamename".format(ctx.author.name))
                else:
                    self.sublist[np.where(twitchnames(self.sublist)==ctx.author.name.lower())] = ctx.author.name.lower()+"🔥"+' '.join(templist[1:]).lower()
                    await ctx.channel.send("@{} I've changed your in game name to {}".format(ctx.author.name, ' '.join(templist[1:]).lower()))
                    backuplog(self.sublist, "backupsublog.csv")
            else:
                await ctx.channel.send("@{} you're not in the queue".format(ctx.author.name))

    @commands.command(name='changename')
    async def changename(self,ctx): # If a user input their name wrong when joining, a moderator can use !changename twitchname newingamename to fix the mishap.
        if ctx.author.is_mod:
            templist = ctx.message.content.split(' ')
            if templist[1].lower() in twitchnames(self.playerqueue):
                if len(templist) < 3:
                    await ctx.channel.send("@{} not enough positional arguments. It's !changename twitchname newingamename".format(ctx.author.name))
                else:
                    self.playerqueue[np.where(twitchnames(self.playerqueue)==templist[1].lower())] = templist[1].lower()+"🔥"+' '.join(templist[2:]).lower()
                    await ctx.channel.send("@{} I've changed @{}'s in game name to {}".format(ctx.author.name, templist[1].lower(), ' '.join(templist[2:]).lower()))
                    backuplog(self.playerqueue, "backuplog.csv")
            elif templist[1].lower() in twitchnames(self.sublist):
                if len(templist) < 3:
                    await ctx.channel.send("@{} not enough positional arguments. It's !changename twitchname newingamename".format(ctx.author.name))
                else:
                    self.sublist[np.where(twitchnames(self.sublist)==templist[1].lower())] = templist[1].lower()+"🔥"+' '.join(templist[2:]).lower()
                    await ctx.channel.send("@{} I've changed @{}'s in game name to {}".format(ctx.author.name, templist[1].lower(), ' '.join(templist[2:]).lower()))
                    backuplog(self.sublist, "backupsublog.csv")
            else:
                await ctx.channel.send("@{} I couldn't find this user in the queue".format(ctx.author.name))

    @commands.command(name='plug')
    async def plug(self,ctx): # !plug twitchname switchname is a moderator only command to insert someone into the queue.
        if ctx.author.is_mod:
            if ' ' in ctx.message.content:
                templist = ctx.message.content.split(' ')
                if templist[1].lower() in twitchnames(self.playerqueue):
                    await ctx.channel.send("{} is already in the queue".format(templist[1]))
                elif len(templist) < 3:
                    await ctx.channel.send("@{} not enough positional arguments. It's [!plug twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))
                elif not intchecker(templist[-1]):
                    self.playerqueue = np.append(self.playerqueue,templist[1].lower()+"🔥"+' '.join(templist[2:]).lower())
                    backuplog(self.playerqueue, "backuplog.csv")
                    if self.playerqueue[-1] in self.played:
                        self.played.discard(self.playerqueue[-1].split("🔥")[0])
                    await ctx.channel.send("{} has been added to the queue at the back".format(self.playerqueue[-1]))
                else:
                    self.playerqueue = np.insert(self.playerqueue,int(templist[-1]), templist[1].lower()+"🔥"+' '.join(templist[2:-1]).lower())
                    if templist[1].lower() in self.played:
                        self.played.discard(templist[1].lower())
                    await ctx.channel.send("{} has been added to the queue at position {}".format(' '.join(templist[2:-1]).lower(), templist[-1]))
            else:
                await ctx.channel.send("@{} not enough positional arguments. It's [!plug twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))

    @commands.command(name='plugsub')
    async def plugsub(self,ctx):
        if ctx.author.is_mod: # !plugsub twitchname switchname is a moderator only command used to plug someone into the self.sublist.
            if "check !showsubs🔥check !showsubs" not in self.playerqueue:
                self.playerqueue = np.insert(self.playerqueue,1,"check !showsubs🔥check !showsubs")
            if ' ' in ctx.message.content:
                templist = ctx.message.content.split(' ')
                if templist[1].lower() in twitchnames(self.sublist):
                    await ctx.channel.send("{} is already in the queue".format(templist[1]))
                elif len(templist) < 3:
                    await ctx.channel.send("@{} not enough positional arguments. It's [!plugsub twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))
                elif not intchecker(templist[-1]):
                    self.sublist = np.append(self.sublist,templist[1].lower()+"🔥"+' '.join(templist[2:]).lower())
                    backuplog(self.sublist, "backupsublog.csv")
                    if self.sublist[-1] in self.played:
                        self.played.discard(self.sublist[-1].split("🔥")[0])
                    await ctx.channel.send("{} has been added to the sublist at the back".format(self.sublist[-1]))
                else:
                    self.sublist = np.insert(self.sublist,int(templist[-1]), templist[1].lower()+"🔥"+' '.join(templist[2:-1]).lower())
                    if templist[1].lower() in self.played:
                        self.played.discard(templist[1].lower())
                    await ctx.channel.send("{} has been added to the sublist at position {}".format(' '.join(templist[2:-1]).lower(), templist[-1]))
            else:
                await ctx.channel.send("@{} not enough positional arguments. It's [!plugsub twitchname switchname position] without the [ ] (position is optional). If no information is provided on Twitch name, use 'NULL' instead".format(ctx.author.name))

    @commands.command(name='plugplayed')
    async def plugplayed(self,ctx): # !plugplayed switchname twitchname is a moderator only command to add a user to the set of players who already played.
        if ctx.author.is_mod:
            if ' ' in ctx.message.content:
                templist = ctx.message.content.split(' ')
                if templist[1].lower() in self.played:
                    await ctx.channel.send("{} is already in the played list".format(templist[1]))
                elif len(templist) < 2:
                    await ctx.channel.send("@{} not enough positional arguments. It's [!plugplayed twitchname] without the [ ]. If no information is provided on Twitch name, just use their Switch name as a placeholder".format(ctx.author.name))
                else:
                    self.played.add(templist[1].lower())
                    await ctx.channel.send("{} has been added to the played list".format(templist[1].lower()))
            else:
                await ctx.channel.send("@{} not enough positional arguments. It's [!plugplayed twitchname] without the [ ]. If no information is provided on Twitch name, just use their Switch name as a placeholder".format(ctx.author.name))

    @commands.command(name='fillqueue')
    async def fillqueue(self,ctx): # In the event the program needs to be rerun, the data can be immediately loaded from backuplog.csv, which is updated alongside the queue.
        if ctx.author.is_mod:
            with open("backuplog.csv", 'r') as f:
                for person in f.read().split('\n'):
                    if ',' in person:
                        self.playerqueue = np.append(self.playerqueue,person.replace(',',"🔥"))
            await ctx.channel.send("@{} the queue has been restored".format(ctx.author.name))

    @commands.command(name='fillsubs')
    async def fillsubs(self,ctx): # Similarly to the above command, !fillsubs is used to restore the self.sublist.
        if ctx.author.is_mod:
            with open("backupsublog.csv", 'r') as f:
                for person in f.read().split('\n'):
                    if ',' in person:
                        self.sublist = np.append(self.sublist,person.replace(',',"🔥"))
            await ctx.channel.send("@{} the subs list has been restored".format(ctx.author.name))

bot = Bot()
bot.run()