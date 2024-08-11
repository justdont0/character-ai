import os
import disnake
from disnake.ext import commands
import json
from characterai import PyAsyncCAI
from pprint import pprint
import os
from disnake.interactions.modal import ModalInteraction
from dotenv import load_dotenv

load_dotenv()
bot = commands.InteractionBot()
client = PyAsyncCAI(os.getenv('ctoken'))
db = json.load(open('chai.json'))

async def get_id(link: str) -> dict | list[dict]:
    try:
        char = await client.character.info(link.split()[0])
        return char['character']
    except:
        if link.startswith('https://c.ai/c/'):
            return (await client.character.info(link.split('/')[-1]))['character']
        if link.startswith('https://') and link.find('character.ai')!= -1 and '?' in link:
            for param in link.split('?')[1].split('&'):
                if param.startswith('char='):
                    return (await client.character.info(param.split('=')[1]))['character']
        return (await client.character.search(link))['characters'][:10]

@bot.event
async def on_guild_join(guild: disnake.Guild):
    channel = guild.system_channel
    bot_member: disnake.Member = guild.get_member(bot.user.id)
    if channel is None or not channel.permissions_for(bot_member).send_messages:
        for channel in guild.text_channels:
            if channel.permissions_for(bot_member).send_messages: break
    if channel is None:
        print(':-1:')
        return
    await channel.send('# Thank you for inviting Unofficial character.ai bot!')
    json.dump(db, open('chai.json', 'w'))

@bot.event
async def on_dropdown(ctx: disnake.MessageInteraction):
    if ctx.component.custom_id == 'autoanswer':
        await ctx.response.defer()
        char = await get_id(ctx.values[0])
        chat = await client.chat.new_chat(char['external_id'])
        participants = chat['participants']
        if not participants[0]['is_human']:
            tgt = participants[0]['user']['username']
        else:
            tgt = participants[1]['user']['username']
        db['channels'][str(ctx.channel.id)] = {'hist': chat['external_id'], 'tgt': tgt, 'avatar': f"https://characterai.io/i/80/static/avatars/{char['avatar_file_name']}"}
        json.dump(db, open('chai.json', 'w'))
        embed = disnake.Embed(title=char['name'], description=char['description'], color=disnake.Color.green())
        embed.set_thumbnail(f"https://characterai.io/i/80/static/avatars/{char['avatar_file_name']}")
        await ctx.followup.send(f"Autoanswer character have been set to **{char['name']}**", embed=embed)

@bot.event
async def on_message(message: disnake.Message):
    if str(message.channel.id) not in db['channels'] or message.author.bot:
        return
    channel = db['channels'][str(message.channel.id)]
    if message.guild is None or not message.channel.permissions_for(message.guild.get_member(bot.user.id)).manage_webhooks:
        data = await client.chat.send_message(channel['hist'], channel['tgt'], message.content)
        return
    webhook = disnake.utils.find(lambda hook: hook.user.id == bot.user.id, await message.guild.webhooks())
    if webhook is None:
        webhook = await message.channel.create_webhook(name='c.ai')
    elif webhook.channel != message.channel:
        await webhook.edit(channel=message.channel)
    data = await client.chat.send_message(channel['hist'], channel['tgt'], message.content)
    pprint(data['src_char']['participant'])
    await webhook.send(data['replies'][0]['text'], username=data['src_char']['participant']['name'], avatar_url=channel['avatar'])

def heh(ctx: disnake.ApplicationCommandInteraction, text: str):
    resp = [text, 'None'] if text.lower() in 'none' and text != '' else ['None' if text == '' or text.isspace() else text]
    if db['autocorrect'].get(str(ctx.user.id)) is not None: resp.extend(db['autocorrect'].get(str(ctx.user.id)))
    return resp

@bot.slash_command(description='Set automatic character answer for this channel.')
async def setautoanswer(ctx: disnake.ApplicationCommandInteraction, character: str = commands.Param(description='Character ID, c.ai/character.ai link or search query', autocomplete=heh)):
    await ctx.response.defer(ephemeral=True)
    if not ctx.permissions.manage_channels: await ctx.send('You do not have permission to do that.', ephemeral=True)
    char = await get_id(character) if character != 'None' else None
    if char is None:
        if str(ctx.channel.id) in db['channels']:
            del db['channels'][str(ctx.channel.id)]
            json.dump(db, open('chai.json', 'w'))
        await ctx.send('Autoanswer have been disabled for this channel.')
    elif type(char) is dict:
        chat = await client.chat.new_chat(char['external_id'])
        participants = chat['participants']
        if not participants[0]['is_human']:
            tgt = participants[0]['user']['username']
        else:
            tgt = participants[1]['user']['username']
        db['channels'][str(ctx.channel.id)] = {'hist': chat['external_id'], 'tgt': tgt, 'avatar': f"https://characterai.io/i/80/static/avatars/{char['avatar_file_name']}"}
        json.dump(db, open('chai.json', 'w'))
        # pprint(char)
        embed = disnake.Embed(title=char['name'], description=char['description'], color=disnake.Color.green())
        embed.set_thumbnail(f"https://characterai.io/i/80/static/avatars/{char['avatar_file_name']}")
        await ctx.send('Autoanswer have been enabled')
        await ctx.channel.send(f"Autoanswer character have been set to **{char['name']}**", embed=embed, ephemeral=False) # https://characterai.io/i/80/static/avatars/{char['avatar_file_name']}
    else:
        # pprint(char[0])
        select = disnake.ui.StringSelect(custom_id='autoanswer', placeholder='Select character', options=[disnake.SelectOption(label=i['participant__name'], value=i['external_id'], description=i['title']) for i in char])
        await ctx.send('Search results:', components=[select])

bot.run(os.environ['dtoken'])