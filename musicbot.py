import nextcord
import yt_dlp
import asyncio
from nextcord.ext import commands
from nextcord.ext import tasks
from nextcord import FFmpegPCMAudio

# Configuration
TOKEN = 'yourtoken'
FFMPEG_PATH = '/opt/homebrew/bin/ffmpeg'
FFMPEG_OPTIONS = {
    'executable': FFMPEG_PATH,
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.7"'  # Default volume is 70%
}
YT_DL_OPTIONS = {'format': 'bestaudio/best'}

intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

queues = {}
voice_clients = {}
ytdl = yt_dlp.YoutubeDL(YT_DL_OPTIONS)

last_playback = {}

@tasks.loop(seconds=60)
async def check_voice_channel():
    for vc in bot.voice_clients:
        # Check if only the bot is in the voice channel
        if len(vc.channel.members) == 1 and not vc.is_playing():
            # Check if the bot has been idle for more than 60 seconds
            guild_id = vc.guild.id
            last_played = last_playback.get(guild_id, 0)
            current_time = asyncio.get_event_loop().time()
            if current_time - last_played > 60:
                await vc.disconnect()
                print(f'Left the voice channel {vc.channel} because it was empty and idle for 60 seconds.')

@bot.event
async def on_ready():
    await bot.change_presence(status=nextcord.Status.idle, activity=nextcord.Activity(type=nextcord.ActivityType.listening, name='You Gooning'))
    check_voice_channel.start()  # Start the background task
    print(f'{bot.user} is now online and ready to play music!')

@bot.command()
async def join(ctx):
    """Makes the bot join the voice channel and deafen itself."""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()

        # Deafen the bot
        await ctx.guild.change_voice_state(channel=ctx.voice_client.channel, self_deaf=True)
        await ctx.send(f'Joined {channel}.')
    else:
        await ctx.send('You are not connected to a voice channel.')


queues = {}

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = asyncio.Queue()
    return queues[guild_id]

async def play_next(ctx):
    queue = get_queue(ctx.guild.id)
    if queue.empty():
        return
    data = await queue.get()
    song_url = data['url']
    player = nextcord.FFmpegOpusAudio(song_url, **FFMPEG_OPTIONS)
    ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
    await ctx.send(f'Now playing: {data["title"]}')



@bot.command()
async def play(ctx, *, query):
    """Plays a song from YouTube or adds it to the queue if a song is already playing."""
    if not ctx.voice_client:
        await ctx.send('I am not connected to a voice channel.')
        return
    
    def is_url(string):
        return string.startswith('http://') or string.startswith('https://')

    try:
        if is_url(query):
            data = ytdl.extract_info(query, download=False)
        else:
            data = ytdl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
        
        queue = get_queue(ctx.guild.id)
        await queue.put(data)

        if not ctx.voice_client.is_playing():
            await play_next(ctx)
        else:
            await ctx.send(f'Added to queue: {data["title"]}')
    except Exception as e:
        await ctx.send(f'Error: {e}')
        print(f'Error: {e}')


@bot.command()
async def pause(ctx):
    """Pauses the currently playing song."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send('Paused the current track.')
    else:
        await ctx.send('No track is currently playing.')

@bot.command()
async def resume(ctx):
    """Resumes the currently paused song."""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send('Resumed the current track.')
    else:
        await ctx.send('No track is currently paused.')

@bot.command()
async def stop(ctx):
    """Stops the currently playing song and clears the queue."""
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send('Stopped the current track.')
    else:
        await ctx.send('No track is currently playing.')

@bot.command()
async def skip(ctx):
    """Skips the currently playing song."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send('Skipped the current track.')
        await play_next(ctx)
    else:
        await ctx.send('No track is currently playing.')


@bot.command()
async def queue(ctx):
    """Displays the current queue."""
    queue = get_queue(ctx.guild.id)
    if queue.empty():
        await ctx.send('The queue is empty.')
    else:
        queued_titles = []
        for item in queue._queue:
            queued_titles.append(item['title'])
        await ctx.send(f'Current queue:\n' + '\n'.join(queued_titles))

bot.run(TOKEN)
