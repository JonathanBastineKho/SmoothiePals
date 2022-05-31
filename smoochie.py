import discord
from datetime import datetime
from discord.ext import commands
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv
load_dotenv()

# -------- GLOBAL VARIABLES -------- #

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = int(os.getenv('GUILD'))
RAFFLE = int(os.getenv('RAFFLE_ROLE'))
DATABASE = os.getenv('DATABASE')
TEXT_CHANNEL = int(os.getenv('TEXT_CHANNEL'))

# -------- DATABASE -------- #

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Totals(db.Model):
    inviter_id = db.Column(db.Integer, unique=True)
    normal = db.Column(db.Integer)
    left = db.Column(db.Integer)
    fake = db.Column(db.Integer)
    Primary_Key = db.Column(db.Integer, primary_key=True)

class Invites(db.Model):
    id = db.Column(db.String(250), unique=True)
    uses = db.Column(db.Integer)
    Primary_Key = db.Column(db.Integer, primary_key=True)

class Joined(db.Model):
    inviter_id = db.Column(db.Integer)
    joiner_id = db.Column(db.Integer, unique=True)
    Primary_Key = db.Column(db.Integer, primary_key=True)

db.create_all()

# -------- DISCORD -------- #

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print("I am ready")

    member_list = []
    for guild in bot.guilds:
        for member in guild.members:
            member_list.append(member.id)

    for i in Joined.query.all():
        if i.joiner_id not in member_list:
            joined_to_delete = Joined.query.filter_by(joiner_id=i.joiner_id).first()
            inviter_to_decrease = joined_to_delete.inviter_id
            totals_to_decrease = Totals.query.filter_by(inviter_id=inviter_to_decrease).first()
            totals_to_decrease.left += 1
            db.session.delete(joined_to_delete)
            db.session.commit()

async def setup():
    await bot.wait_until_ready()
    for guild in bot.guilds:
        for invite in await guild.invites():
            
            if Invites.query.filter_by(id=invite.id).first() == None:
                db.session.add(Invites(id=invite.id, uses=invite.uses))
                db.session.commit()

            if Totals.query.filter_by(inviter_id=invite.inviter.id).first() == None:
                db.session.add(Totals(inviter_id=invite.inviter.id, normal=0, left=0, fake=0))
                db.session.commit()
        initial_invite = [invite.id for invite in await guild.invites()]
        for i in db.session.query(Invites).all():
            if i.id not in initial_invite:
                db.session.delete(Invites.query.filter_by(id=i.id).first())
                db.session.commit()

@bot.event
async def on_member_join(member):
    invites = await member.guild.invites()
    date = datetime.today().strftime("%Y-%m-%d-%H").split("-")
    y = int(date[0])
    m = int(date[1])
    d = int(date[2])
    h = int(date[3])

    old_invites = db.session.query(Invites).all()
    for invite in invites:
        for old_invite in old_invites:
            if invite.id == old_invite.id and invite.uses - old_invite.uses > 0:
                if not (y == member.created_at.year and m == member.created_at.month and d == member.created_at.day and h - member.created_at.hour <= 7):
                    invite_to_update = Invites.query.filter_by(id=invite.id).first()
                    invite_to_update.uses += 1
                    total_to_update = Totals.query.filter_by(inviter_id=invite.inviter.id).first()
                    total_to_update.normal += 1
                    db.session.commit()
                    role = bot.get_guild(GUILD).get_role(RAFFLE)
                    if total_to_update.normal - total_to_update.left >= 1 and role not in member.roles:
                        m = bot.get_guild(GUILD).get_member(invite.inviter.id)
                        await m.add_roles(role) # --> int(RAFFLE role

                    if Joined.query.filter_by(inviter_id=invite.inviter.id).first() == None or Joined.query.filter_by(joiner_id=member.id).first() == None:
                        print(datetime.today().strftime("%Y-%m-%d-%H-%S") + " added Joined")
                        db.session.add(Joined(inviter_id=invite.inviter.id, joiner_id=member.id))
                        db.session.commit()
                else:
                    total_to_update = Totals.query.filter_by(inviter_id=invite.inviter.id).first()
                    total_to_update.fake += 1
                return

@bot.event
async def on_member_remove(member):
    joined_to_delete = Joined.query.filter_by(joiner_id=member.id).first()
    inviter = joined_to_delete.inviter_id
    db.session.delete(joined_to_delete)
    if Totals.query.filter_by(inviter_id=member.id).first() != None:
        db.session.delete(Totals.query.filter_by(inviter_id=member.id).first())

    totals_to_update = Totals.query.filter_by(inviter_id=inviter).first()
    totals_to_update.left += 1
    db.session.commit()

    inviter_object = bot.get_guild(GUILD).get_member(inviter) # get_guild(guild ID)
    role = bot.get_guild(GUILD).get_role(RAFFLE)
    if totals_to_update.normal - totals_to_update.left < 1 and role in inviter_object.roles:
        await inviter_object.remove_roles(role)

@bot.event
async def on_invite_create(invite):
    if Totals.query.filter_by(inviter_id=invite.inviter.id).first() == None:
        db.session.add(Totals(inviter_id=invite.inviter.id, normal=0, left=0, fake=0))
        db.session.commit()

    if Invites.query.filter_by(id=invite.id).first() == None:
        db.session.add(Invites(id=invite.id, uses=invite.uses))
        db.session.commit()

@bot.event
async def on_invite_delete(invite):
    db.session.delete(Invites.query.filter_by(id=invite.id).first())
    db.session.commit()

@bot.command()
async def invite(ctx, member=None):
    invite_text_channel = bot.guilds[0].get_channel(TEXT_CHANNEL)
    m = None
    if member == None:
        m = bot.get_guild(GUILD).get_member_named(ctx.message.author.name)
    else:
        m = bot.get_guild(GUILD).get_member_named(member)
    if m == None or Totals.query.filter_by(inviter_id=m.id).first() == None:
        embed = discord.Embed(
            title="Invite Statistics",
            description=f"Sorry the member you requested has not created any invite links yet",
            color=discord.Color.red()
            )
    else:
        totals_to_display = Totals.query.filter_by(inviter_id=m.id).first()
        embed = discord.Embed(
            title="Invite Statistics",
            description=f"Below data shows how many people {m.name} have invited to the server",
            color=discord.Color.blue()
            )
        embed.set_author(name=m.name, icon_url=m.avatar_url)
        embed.set_thumbnail(url="https://img.icons8.com/external-bearicons-flat-bearicons/64/000000/external-Invitation-christmas-and-new-year-bearicons-flat-bearicons.png")
        embed.add_field(name=f"Total Invite: {totals_to_display.normal - totals_to_display.left}", inline=False, value=f"Number of invites that {m.name} has")
        embed.add_field(name=f"Joined: {totals_to_display.normal}", inline=True, value=f"Number of members joined via {m.name}'s link")
        embed.add_field(name=f"Left: {totals_to_display.left}", inline=True, value=f"Number of members who left")
        embed.add_field(name=f"Suspicious: {totals_to_display.fake}", inline=True, value="Number of Sus invites")
        date = datetime.today().strftime("%Y-%m-%d  %H:%M:%S (SGT)")
        embed.set_footer(text=date)
    
    if int(ctx.channel.id) != TEXT_CHANNEL:
        embed2 = discord.Embed(
            title="Hey",
            description="Head over to the invite-log text channel",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed2)

    await invite_text_channel.send(f"{ctx.message.author.mention}") 
    await invite_text_channel.send(embed=embed)

bot.loop.create_task(setup())
bot.run(TOKEN)