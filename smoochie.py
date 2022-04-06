from enum import unique
import sqlite3
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
GUILD = os.getenv('GUILD')
RAFFLE = os.getenv('RAFFLE_ROLE')
DATABASE = os.getenv('DATABASE')

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
bot = commands.Bot(command_prefix=',', intents=intents)

@bot.event
async def on_ready():
    print("I am ready")

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
                if not (y == member.created_at.year and m == member.created_at.month and d == member.created_at.day and h - member.created_at.hour <= 1):
                    invite_to_update = Invites.query.filter_by(id=invite.id).first()
                    invite_to_update.uses += 1
                    total_to_update = Totals.query.filter_by(inviter_id=invite.inviter.id).first()
                    total_to_update.normal += 1
                    db.session.commit()
                    role = bot.get_guild(GUILD).get_role(RAFFLE)
                    if total_to_update.normal - total_to_update.left >= 5 and role not in member.roles:
                        m = bot.get_guild(GUILD).get_member(invite.inviter.id)
                        await m.add_roles(role) # --> Raffle role

                    if Joined.query.filter_by(inviter_id=invite.inviter.id).first() == None or Joined.query.filter_by(joiner_id=member.id).first() == None:
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
    if totals_to_update.normal - totals_to_update.left < 5 and role in inviter_object.roles:
        await inviter_object.remove_roles(role)

async def on_invite_create(invite):
    if Totals.query.filter_by(inviter_id=invite.inviter.id).first() == None:
        db.session.add(Totals(inviter_id=invite.inviter.id, normal=0, left=0, fake=0))
        db.session.commit()

    if Invites.query.filter_by(id=invite.id).first() == None:
        db.session.add(Invites(id=invite.id, uses=invite.uses))
        db.session.commit()

@bot.event
async def on_invite_delete(invite):
    db.session.delete(Invites.query.filter_by(id=invite.id).first)
    db.session.commit()

bot.loop.create_task(setup())
bot.run(TOKEN)