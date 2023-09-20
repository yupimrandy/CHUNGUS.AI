import asyncio
import discord
import math
import random
from data_extractor import Source, ffmpeg_options, allqueues, extractor

SONGS_PER_PAGE = 5

PLAY_EMOJI = "<:emoji:1149085229399679056>"
PAUSE_EMOJI = "<:emoji:1149939326617129012>"
NEXT_TRACK_EMOJI = "<:emoji:1149085225503182998>"
PREVIOUS_TRACK_EMOJI = "<:emoji:1149085230863487069>"
SHUFFLE_EMOJI = "<:emoji:1149085234919378944>"
REPEAT_EMOJI = "<:emoji:1149085233489129572>"
SEARCH_EMOJI = "<:emoji:1149896596117520495>"
DEL_EMOJI = "<:emoji:1152699399072391238>"
TRASH_EMOJI = "<:emoji:1152704387131658321>"
VOLUME_UP_EMOJI = "<:emoji:1153500722378321940>"
VOLUME_DOWN_EMOJI = "<:emoji:1153500721254240336>"
PLAY_NOW_EMOJI = "<:emoji:1152699402415251546>"
PLAY_NEXT_EMOJI = "<:emoji:1152699400456503377>"
PLAY_NUM_EMOJI = "<:emoji:1152699403744845885>"
ADD_EMOJI = "<:emoji:1152699395159101631>"
MUTE_EMOJI = "<:emoji:1153500717429030952>"
UNMUTE_EMOJI = "<:emoji:1153500718448263249>"
NEXT_PAGE_EMOJI = "<:emoji:1149925447132520490>"
PREVIOUS_PAGE_EMOJI = "<:emoji:1149925448260788274>"
HELP_EMOJI = "<:emoji:1149925445131833345>"
BOT_JOIN = "<:emoji:1150572447817551932>"
BOT_LEAVE = "<:emoji:1150572449356853298>"

class PlayerLogic():
    def __init__(self, interaction:discord.Interaction):
        thisguild = {'guild':discord.Guild,
                    'songtitles':list,
                    'songurls':list,
                    'currentpage':int,
                    'position':int,
                    'nowplaying':str,
                    'volume':float,
                    'priorvolume':float,
                    'isbasic':bool,
                    'islooped':bool,
                    'isstopped':bool}
        self.guild = interaction.guild
        self.index = -1
        for index in range(len(allqueues)):
            if self.guild == allqueues[index]['guild']:
                thisguild = allqueues[index]
                self.index += index+1

        if self.index == -1:
            thisguild['guild'] = self.guild
            thisguild['songtitles'] = []
            thisguild['songurls'] = []
            thisguild['currentpage'] = 1
            thisguild['position'] = 0
            thisguild['nowplaying'] = ""
            thisguild['volume'] = 1.0
            thisguild['priorvolume'] = 1.0
            thisguild['isbasic'] = False
            thisguild['islooped'] = False
            thisguild['isstopped'] = False
            allqueues.append(thisguild)
            self.index == len(allqueues)-1

        self.voiceclient = interaction.guild.voice_client
        self.message = interaction.message
        self.position = allqueues[self.index]['position']
        self.currentpage = allqueues[self.index]['currentpage']
        self.nowplaying = allqueues[self.index]['nowplaying']
        self.volume = allqueues[self.index]['volume']
        self.priorvolume = allqueues[self.index]['priorvolume']
        self.islooped = allqueues[self.index]['islooped']
        self.isbasic = allqueues[self.index]['isbasic']
        self.isstopped = allqueues[self.index]['isstopped']
        self.songtitles = allqueues[self.index]['songtitles']
        self.songurls = allqueues[self.index]['songurls']
        self.maxpage = (len(self.songtitles)/SONGS_PER_PAGE)
        self.maxpage = math.ceil(self.maxpage)
        if self.maxpage == 0:
            self.maxpage = 1
    
    @classmethod
    async def player(cls, interaction:discord.Interaction, message:discord.Message, stop=False):
        guild = PlayerLogic(interaction)
        if guild.voiceclient == None or len(guild.songtitles) == 0:
            return

        if guild.voiceclient.is_playing():
            guild.voiceclient.pause()

        songtitle = guild.songtitles[guild.position]
        songurl = guild.songurls[guild.position]
        if asyncio.get_event_loop() == None:
            loop = asyncio.new_event_loop()
        else:
            loop = asyncio.get_event_loop()

        allqueues[guild.index]['nowplaying'] = songtitle

        if songurl == songtitle or songurl.replace(" explicit", "") == songtitle:
            data = await loop.run_in_executor(None, lambda: extractor.extract_info(f"ytsearch:{songurl}", download=False))
            songurl = data["entries"][0]["url"]
        streamurl = await Source.stream_url(songurl)

        if guild.position+1 > guild.currentpage*10:
            allqueues[guild.index]['currentpage'] = math.ceil((guild.position+1)/10)

        embed = await PlayerLogic.build_page(interaction, playing=True)
        if message == None:
            message = await interaction.followup.send(embed=embed, view=await PlayerLogic.build_view(interaction, playing=True))
        else:
            await message.edit(embed=embed, view=await PlayerLogic.build_view(interaction, playing=True))
        guild.voiceclient.play(discord.FFmpegPCMAudio(streamurl, **ffmpeg_options), after=lambda error: loop.create_task(PlayerLogic.check_queue(interaction, message)))
        guild.voiceclient.source = discord.PCMVolumeTransformer(guild.voiceclient.source, guild.volume)

    @classmethod
    async def check_queue(cls, interaction:discord.Interaction, message:discord.Message):
        guild = PlayerLogic(interaction)                 
        allqueues[guild.index]['nowplaying'] = ""
        
        if guild.voiceclient == None or guild.voiceclient.is_paused():
            return
        elif guild.voiceclient.is_playing():
            guild.voiceclient.stop()

        if guild.position < len(guild.songtitles)-1 and len(guild.songtitles) > 0:
            allqueues[guild.index]['position'] += 1
            await PlayerLogic.player(interaction, message)
        elif allqueues[guild.index]['islooped'] and len(guild.songtitles) > 0:
            allqueues[guild.index]['position'] = 0
            allqueues[guild.index]['currentpage'] = 1
            await PlayerLogic.player(interaction, message)
        else:
            embed = await PlayerLogic.build_page(interaction)
            await message.edit(embed=embed, view=await PlayerLogic.build_view(interaction))

    @classmethod
    async def build_page(cls, interaction:discord.Interaction, playing=False, previouspage=False, nextpage=False, goto=False, voiceclient=None):
        guild = PlayerLogic(interaction)
        if guild.voiceclient == None and voiceclient == None:
            return
        elif guild.voiceclient == None:
            guild.voiceclient = voiceclient

        if (guild.voiceclient.is_playing() or playing) and not (previouspage or nextpage or goto):
            guild.currentpage = math.ceil((guild.position+1)/SONGS_PER_PAGE)
        firstsong = (guild.currentpage-1)*SONGS_PER_PAGE
        lastsong = ((guild.currentpage-1)*SONGS_PER_PAGE) + SONGS_PER_PAGE
        songlist = ""
        songcount = len(guild.songtitles)

        embed = discord.Embed(
                            title=("[CHUNGUS.AI Player BETA]"),
                            color=discord.Color.red(),
                            )

        for index, song in enumerate(guild.songtitles[firstsong:lastsong]):
            if (index+((guild.currentpage-1)*SONGS_PER_PAGE)) == guild.position and (guild.voiceclient.is_playing() or playing) and song == guild.nowplaying:
                songtitle = "**[" + str(index + 1 + ((guild.currentpage - 1) * SONGS_PER_PAGE)) + "] " + str(song) + "**" + "\n"
            else:
                songtitle = "[" + str(index + 1 + ((guild.currentpage - 1) * SONGS_PER_PAGE)) + "] " + str(song) + "\n"
            songlist += songtitle

        if len(songlist) > 0:
            songlist[:-2]
        if allqueues[guild.index]['islooped']:
            loopvalue = "On"
        else:
            loopvalue = "Off"
        if not guild.isbasic:
            embed.add_field(name=("Page " + str(guild.currentpage) + " / " + str(guild.maxpage)), value=songlist, inline=False)
        embed.add_field(name="Songs Queued", value=str(songcount), inline=True)
        embed.add_field(name="Volume", value=(str(int(guild.volume*100)) + "%"), inline=True)
        embed.add_field(name="Loop", value=loopvalue, inline=True)
        if guild.voiceclient.is_playing() or playing:
            embed.add_field(name="Now Playing", value=guild.nowplaying, inline=True)
            if len(guild.songtitles) > (guild.position+1):
                embed.add_field(name="Up Next", value=guild.songtitles[guild.position+1], inline=True)
            elif guild.islooped and guild.position == len(guild.songtitles)-1:
                embed.add_field(name="Up Next", value=guild.songtitles[0], inline=True)
        
        return embed

    @classmethod
    async def build_view(cls, interaction: discord.Interaction, playing=False, leave=False, voiceclient=None):
        guild = PlayerLogic(interaction)
        if guild.voiceclient == None and voiceclient == None:
            return
        elif guild.voiceclient == None:
            guild.voiceclient = voiceclient
        
        view = PlayerView(timeout=None)
        pausebutton = AltView().children[0]
        mutebutton = AltView().children[1]
        joinbutton = AltView().children[2]

        if (guild.voiceclient.is_playing() or playing) and not leave:
            children = []
            for child in range(0, 13):
                child = view.children.pop()
                children.append(child)
                view.remove_item(child)
            view.add_item(pausebutton)
            children.pop()
            for child in range(0, 12):
                view.add_item(children.pop())
        if guild.volume == 0:
            children = []
            for child in range(0, 8):
                child = view.children.pop()
                children.append(child)
                view.remove_item(child)
            view.add_item(mutebutton)
            children.pop()
            for child in range(0, 7):
                view.add_item(children.pop())
        if leave:
            children = []
            for child in range(0, 4):
                child = view.children.pop()
                children.append(child)
                view.remove_item(child)
            view.add_item(joinbutton)
            children.pop()
            for child in range(0, 3):
                view.add_item(children.pop())
        if guild.isbasic == True:
            for child in range(0, 5):
                view.remove_item(view.children.pop())

        return view
    
    @classmethod
    async def process_input(cls, interaction:discord.Interaction, arg="", 
                            next=False, 
                            now=False, 
                            page=False, 
                            delete=False, 
                            add=False, 
                            song=False, 
                            mute=False,
                            volumeup=False,
                            volumedown=False,
                            nextpage=False,
                            previouspage=False,
                            nexttrack=False,
                            previoustrack=False,
                            shuffle=False,
                            play=False,
                            clear=False,
                            join=False,
                            leave=False,
                            loop=False,
                            basicplayer=False,
                            expandedplayer=False):
        try:
            await interaction.response.defer()
        finally:
            guild = PlayerLogic(interaction)
            if basicplayer or expandedplayer:
                guild.voiceclient = await PlayerLogic.in_voice_channel(interaction, join=True)
            if guild.voiceclient == None and not join:
                return
            
            messagetosend = ""
            unshuffled_titles = guild.songtitles
            unshuffled_urls = guild.songurls
            shuffled_titles = []
            shuffled_urls = [] 
            embed = await PlayerLogic.build_page(interaction)  
            if page or delete or song:
                if page:
                    if arg <= guild.maxpage:
                        allqueues[guild.index]['currentpage'] = arg
                        embed = await PlayerLogic.build_page(interaction, goto=True)
                    elif arg > guild.maxpage:
                        embed.add_field(name="The number entered is greater than the number of pages.", value="", inline=False)

                elif delete:
                    deletedtitle = guild.songtitles[arg-1]

                    if guild.voiceclient.is_playing():
                        if guild.position == (arg-1):
                            allqueues[guild.index]['position'] -= 1

                    del allqueues[guild.index]['songtitles'][arg-1]
                    del allqueues[guild.index]['songurls'][arg-1]

                    embed = await PlayerLogic.build_page(interaction)
                    embed.add_field(name=('"' + deletedtitle + '"' + " was deleted from the queue."), value="", inline=False)
                
                elif song:
                    if arg > len(guild.songtitles):
                        embed.add_field(name="The number entered is greater than the number of songs.", value="", inline=False)
                    elif len(guild.songtitles) > 0:
                        allqueues[guild.index]['position'] = (arg-1)
                        if guild.voiceclient.is_playing():
                            interaction.guild.voice_client.pause()
                        await PlayerLogic.player(interaction, guild.message)
                        return

            elif add or now or next:
                if "playlist" in arg:
                    if next:
                        playlistreportvalues = await Source.add_playlist(arg, guild.index, next=next)
                    elif now:
                        playlistreportvalues = await Source.add_playlist(arg, guild.index, now=now)
                    elif add:
                        playlistreportvalues = await Source.add_playlist(arg, guild.index)

                    playlistreport = str(playlistreportvalues[0]) + " songs were added to the queue from this playlist."
                    if playlistreportvalues[1] > 0:
                        playlistreport += "\n" + str(playlistreportvalues[1]) + " were not added due to either being private or unavailable."
                    messagetosend = playlistreport      
                else:
                    if next:
                        messagetosend = await Source.add_song(arg, guild.index, next=next)
                    elif now:
                        messagetosend = await Source.add_song(arg, guild.index, now=now)
                    elif add:
                        messagetosend = await Source.add_song(arg, guild.index)

                embed = await PlayerLogic.build_page(interaction)  
                
                if "from this playlist" in messagetosend:
                    embed.add_field(name=messagetosend, value="", inline=False)
                elif messagetosend != "":
                    embed.add_field(name=('"' + messagetosend + '"' + ' was added to the queue.'), value="", inline=False)

                if now and not (loop or shuffle):
                    guild.voiceclient.pause()
                    await PlayerLogic.player(interaction, guild.message)
                    return

            elif volumeup or volumedown or mute:
                if guild.voiceclient.is_playing():
                    if volumeup and guild.volume < 1:
                        guild.voiceclient.source.volume = guild.volume+0.1
                        allqueues[guild.index]['volume'] = guild.volume+0.1
                    elif volumedown and guild.volume > 0.11:
                        guild.voiceclient.source.volume = guild.volume-0.1
                        allqueues[guild.index]['volume'] = guild.volume-0.1
                    elif mute and guild.volume != 0:
                        allqueues[guild.index]['priorvolume'] = guild.volume
                        guild.voiceclient.source.volume = 0
                        allqueues[guild.index]['volume'] = 0
                        embed = await PlayerLogic.build_page(interaction)
                    elif mute:
                        guild.voiceclient.source.volume = guild.priorvolume
                        allqueues[guild.index]['volume'] = guild.priorvolume
                embed = await PlayerLogic.build_page(interaction)

            elif nextpage or previouspage:
                if nextpage and guild.currentpage < guild.maxpage:
                    allqueues[guild.index]['currentpage'] += 1
                    embed = await PlayerLogic.build_page(interaction, nextpage=nextpage)
                elif previouspage and guild.currentpage > 1:
                    allqueues[guild.index]['currentpage'] -= 1
                    embed = await PlayerLogic.build_page(interaction, previouspage=previouspage)
                else:
                    return

            elif nexttrack or previoustrack:
                if guild.voiceclient.is_playing():
                    if guild.position < len(guild.songtitles)-1 and nexttrack:
                        allqueues[guild.index]['position'] += 1
                    elif guild.position == len(guild.songtitles)-1 and guild.islooped and nexttrack:
                        allqueues[guild.index]['position'] = 0
                    elif guild.position > 0 and previoustrack:
                        allqueues[guild.index]['position'] -= 1
                    elif guild.islooped and previoustrack:
                        allqueues[guild.index]['position'] = len(guild.songtitles)-1
                    await PlayerLogic.player(interaction, guild.message)
                return

            elif play:
                if guild.voiceclient.is_paused():
                    guild.voiceclient.resume()
                    embed = await PlayerLogic.build_page(interaction)
                elif guild.voiceclient.is_playing():
                    guild.voiceclient.pause()
                    embed = await PlayerLogic.build_page(interaction)
                else:
                    guild.voiceclient.pause()
                    await PlayerLogic.player(interaction, guild.message)
                    return
                
            elif clear:
                allqueues[guild.index]['songurls'].clear()
                allqueues[guild.index]['songtitles'].clear()
                allqueues[guild.index]['currentpage'] = 1
                allqueues[guild.index]['position'] = 0
                embed = await PlayerLogic.build_page(interaction)
                
            elif join:
                guild.voiceclient = await PlayerLogic.in_voice_channel(interaction, join=True)
                embed = await PlayerLogic.build_page(interaction, voiceclient=guild.voiceclient) 

            elif leave:
                await PlayerLogic.in_voice_channel(interaction, leave=True)

            elif basicplayer or expandedplayer:
                if basicplayer:
                    if guild.isbasic != True:
                        allqueues[guild.index]['isbasic'] = True
                else:
                    if guild.isbasic != False:
                        allqueues[guild.index]['isbasic'] = False
                    
                if guild.currentpage > guild.maxpage:
                    guild.currentpage = guild.maxpage

                if arg != None:
                    await PlayerLogic.process_input(interaction, arg=arg, now=True, shuffle=shuffle, loop=loop)
                    return
                else:    
                    embed = await PlayerLogic.build_page(interaction)                 

            if loop:
                if allqueues[guild.index]['islooped']:
                    allqueues[guild.index]['islooped'] = False
                else:
                    allqueues[guild.index]['islooped'] = True
                if now and not shuffle:
                    await PlayerLogic.player(interaction, guild.message)
                    return
                else:
                    embed = await PlayerLogic.build_page(interaction)

            if shuffle:
                if interaction.guild.voice_client.is_playing():
                    shuffled_titles.append(guild.songtitles.pop(guild.position))
                    shuffled_urls.append(guild.songurls.pop(guild.position))            

                allqueues[guild.index]['position'] = 0

                for x in range(len(unshuffled_titles)):
                    length = (len(unshuffled_titles))-1
                    index = random.randint(0, length)
                    shuffled_titles.append(unshuffled_titles.pop(index))
                    shuffled_urls.append(unshuffled_urls.pop(index))            

                allqueues[guild.index]['songtitles'].clear
                allqueues[guild.index]['songurls'].clear
                for x in range(len(shuffled_titles)):
                    allqueues[guild.index]['songtitles'].append(shuffled_titles[x])
                    allqueues[guild.index]['songurls'].append(shuffled_urls[x])
                if now:
                    await PlayerLogic.player(interaction, guild.message)
                    return
                else:
                    embed = await PlayerLogic.build_page(interaction)

        if guild.message == None:
            await interaction.followup.send(embed=embed, view=await PlayerLogic.build_view(interaction))
        elif leave:
            await guild.message.edit(embed=embed, view=await PlayerLogic.build_view(interaction, leave=True))
        else:
            await guild.message.edit(embed=embed, view=await PlayerLogic.build_view(interaction))

    async def in_voice_channel(interaction:discord.Interaction, join=False, leave=False):
        if not interaction.user.voice:
            await interaction.followup.send("You must be connected to a voice channel.")
            return None 
        elif interaction.guild.voice_client == None:
            if join:
                voiceclient = await interaction.user.voice.channel.connect()
                voiceclient.play(discord.FFmpegPCMAudio(executable="ffmpeg", source="assets/VOICE_CLIPS/ello_mates.webm"))
                await asyncio.sleep(1.5)
                voiceclient.stop()
                return voiceclient    
            else:
                return await interaction.user.voice.channel.connect()
        elif leave:
            if asyncio.get_event_loop() == None:
                loop = asyncio.new_event_loop()
            else:
                loop = asyncio.get_event_loop()

            async def wait_to_disconnect():
                if not voiceclient.is_playing():
                    await voiceclient.disconnect()
            
            voiceclient = interaction.guild.voice_client
            if voiceclient.is_playing():
                voiceclient.stop()
            voiceclient.play(discord.FFmpegPCMAudio(executable="ffmpeg", source="assets/VOICE_CLIPS/fuck_ya_then.webm"), after=lambda error: loop.create_task(wait_to_disconnect()))
        else:
            return interaction.guild.voice_client

class PlayerView(discord.ui.View):
    @discord.ui.button(label="", style=discord.ButtonStyle.blurple, row=0, emoji=SHUFFLE_EMOJI)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, shuffle=True) 

    @discord.ui.button(label="", style=discord.ButtonStyle.blurple, row=0, emoji=PREVIOUS_TRACK_EMOJI)
    async def previous_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, previoustrack=True) 

    @discord.ui.button(label="", style=discord.ButtonStyle.blurple, row=0, emoji=PLAY_EMOJI)
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, play=True) 
    
    @discord.ui.button(label="", style=discord.ButtonStyle.blurple, row=0, emoji=NEXT_TRACK_EMOJI)
    async def nextsong(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, nexttrack=True) 

    @discord.ui.button(label="", style=discord.ButtonStyle.blurple, row=0, emoji=REPEAT_EMOJI)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, loop=True) 

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, row=1, emoji=ADD_EMOJI)
    async def addsongs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddSongs())

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, row=1, emoji=DEL_EMOJI)
    async def deletenum(self, interaction: discord.Interaction, button: discord.ui.Button):       
        await interaction.response.send_modal(DeleteNumber())

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, row=1, emoji=MUTE_EMOJI)
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, mute=True) 

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, row=1, emoji=VOLUME_DOWN_EMOJI)
    async def volumedown(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, volumedown=True) 

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, row=1, emoji=VOLUME_UP_EMOJI)
    async def volumeup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, volumeup=True) 

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, row=2, emoji=HELP_EMOJI)
    async def help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=await PlayerLogic.build_page(interaction))

    @discord.ui.button(label="", style=discord.ButtonStyle.red, row=2, emoji=BOT_LEAVE)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, leave=True) 

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, row=2, emoji=SEARCH_EMOJI)
    async def page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(Page())

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, row=2, emoji=PREVIOUS_PAGE_EMOJI)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, previouspage=True) 

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, row=2, emoji=NEXT_PAGE_EMOJI)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, nextpage=True) 

class AltView(discord.ui.View):
    @discord.ui.button(label="", style=discord.ButtonStyle.blurple, row=0, emoji=PAUSE_EMOJI)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, play=True) 

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, row=1, emoji=UNMUTE_EMOJI)
    async def unmute(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, mute=True)    

    @discord.ui.button(label="", style=discord.ButtonStyle.green, row=2, emoji=BOT_JOIN)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await PlayerLogic.process_input(interaction, join=True) 

class SongNumber(discord.ui.Modal, title="CHUNGUS.AI"):
    arg = discord.ui.TextInput(label="Enter song's queue position", style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        await PlayerLogic.process_input(interaction, str(self.arg.value), song=True)   

class DeleteNumber(discord.ui.Modal, title="CHUNGUS.AI"):
    arg = discord.ui.TextInput(label="Enter song number or 'ALL'", style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        if "all" in self.arg.value.lower():
            await PlayerLogic.process_input(interaction, int(self.arg.value), delete=True)
        else:
            await PlayerLogic.process_input(interaction, clear=True)

class AddSongs(discord.ui.Modal, title="CHUNGUS.AI"):
    arg = discord.ui.TextInput(label="Enter song name/url/number or playlist url", style=discord.TextStyle.short)
    todo = discord.ui.TextInput(label="Enter 'PLAY', 'NEXT', or 'ADD'", default='PLAY', min_length=3, max_length=4, style=discord.TextStyle.short)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await PlayerLogic.process_input(interaction, int(self.arg.value), song=True)
        except:
            if self.todo.value.lower() == "next":
                await PlayerLogic.process_input(interaction, str(self.arg.value), next=True)
            elif self.todo.value.lower() == "add":
                await PlayerLogic.process_input(interaction, str(self.arg.value), add=True)
            else:  
                await PlayerLogic.process_input(interaction, str(self.arg.value), now=True)     
                        
class Page(discord.ui.Modal, title="CHUNGUS.AI"):
    arg = discord.ui.TextInput(label="Enter a page number", style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        await PlayerLogic.process_input(interaction, int(self.arg.value), page=True) 
