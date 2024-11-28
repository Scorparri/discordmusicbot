import asyncio
import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import random
# Intents are required for accessing certain information
intents = discord.Intents.default()
intents.message_content = True  # Required for message content access

bot = commands.Bot(command_prefix='!', intents=intents)
ffmpeg_options = {
    'executable': r'C:\Users\Nadir\Downloads\ffmpeg-2024-11-25-git-04ce01df0b-full_build\ffmpeg-2024-11-25-git-04ce01df0b-full_build\bin\ffmpeg.exe',  # Adjust the path accordingly
    'options': '-vn',
}

# Configure yt-dlp options
ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'logtostderr': False,
}


ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    """Handles streaming audio from YouTube"""

    def __init__(self, source, *, data, requester, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.requester = requester
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def create_source(cls, url, *, loop, requester, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(url, download=not stream)
        )

        if data is None:
            raise Exception('Could not retrieve any data from the provided URL.')

        sources = []

        if 'entries' in data:
            # It's a playlist or a list of videos
            for entry in data['entries']:
                if entry:
                    filename = entry['url'] if stream else ytdl.prepare_filename(entry)
                    source = cls(
                        discord.FFmpegPCMAudio(filename, **ffmpeg_options),
                        data=entry,
                        requester=requester,
                    )
                    sources.append(source)
        else:
            # It's a single video
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            source = cls(
                discord.FFmpegPCMAudio(filename, **ffmpeg_options),
                data=data,
                requester=requester,
            )
            sources.append(source)

        return sources

song_queue = {}

def get_queue(ctx):
    if ctx.guild.id not in song_queue:
        song_queue[ctx.guild.id] = []
    return song_queue[ctx.guild.id]

def play_next(ctx):
    queue = get_queue(ctx)

    if queue:
        next_song = queue.pop(0)
        ctx.voice_client.play(
            next_song,
            after=lambda e: play_next(ctx)
        )
        coro = ctx.send(f"Now playing: {next_song.title}")
        asyncio.run_coroutine_threadsafe(coro, bot.loop)
    else:
        coro = ctx.voice_client.disconnect()
        asyncio.run_coroutine_threadsafe(coro, bot.loop)

# Bot Commands

@bot.command(name='join', help='Bot joins your voice channel')
async def join(ctx):
    """Joins a voice channel"""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined {channel}")
    else:
        await ctx.send("You're not in a voice channel!")

@bot.command(name='leave', help='Bot leaves the voice channel')
async def leave(ctx):
    """Leaves the voice channel"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel")
    else:
        await ctx.send("I'm not connected to a voice channel.")

@bot.command(name='play', help='Plays a song from YouTube')
async def play(ctx, *, url):
    """Streams music from YouTube"""
    async with ctx.typing():
        if not ctx.voice_client:
            await ctx.invoke(join)

        queue = get_queue(ctx)
        try:
            sources = await YTDLSource.create_source(
                url, loop=bot.loop, requester=ctx.author, stream=True
            )
            queue.extend(sources)

            if not ctx.voice_client.is_playing():
                play_next(ctx)
            else:
                await ctx.send(f'Added to queue: {sources[0].title}')
        except Exception as e:
            print(f'Error: {e}')
            await ctx.send('An error occurred while trying to play the video.')


@bot.command(name='skip', help='Skips the current song')
async def skip(ctx):
    """Skips the current song"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send('Song skipped.')
    else:
        await ctx.send('No song is currently playing.')


@bot.command(name='pause', help='Pauses the current song')
async def pause(ctx):
    """Pauses the audio"""
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused ⏸️")
    else:
        await ctx.send("Nothing is playing.")

@bot.command(name='resume', help='Resumes the current song')
async def resume(ctx):
    """Resumes the audio"""
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed ▶️")
    else:
        await ctx.send("Audio is not paused.")


@bot.command(name='stop', help='Stops the current song and clears the queue')
async def stop(ctx):
    """Stops the audio and clears the queue"""
    get_queue(ctx).clear()
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    await ctx.send("Stopped ⏹️ and cleared the queue.")



@bot.command(name='queue', help='Displays the current song queue')
async def queue_(ctx):
    """Displays the song queue"""
    queue = get_queue(ctx)
    if queue:
        now_playing = ctx.voice_client.source.title if ctx.voice_client and ctx.voice_client.source else 'Nothing'
        queue_length = len(queue)
        display_queue = queue[:10]  # Display only the first 10 songs
        queue_list = [f"{idx + 1}. {song.title} (requested by {song.requester.display_name})" for idx, song in enumerate(display_queue)]
        queue_message = '\n'.join(queue_list)
        if queue_length > 10:
            queue_message += f'\n... and {queue_length - 10} more songs.'
        await ctx.send(f"**Now Playing:** {now_playing}\n\n**Up Next:**\n{queue_message}")
    else:
        await ctx.send('The queue is empty.')


@bot.command(name='shuffle', help='Shuffles the current song queue')
async def shuffle(ctx):
    """Shuffles the song queue"""
    queue = get_queue(ctx)
    if len(queue) > 1:
        random.shuffle(queue)
        await ctx.send('The queue has been shuffled.')
    else:
        await ctx.send('Not enough songs in the queue to shuffle.')
# Run the bot with your token
bot.run('')
