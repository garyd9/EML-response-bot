from bot_functions.manage_players import ManagePlayers
from bot_functions.manage_teams import ManageTeams
from database.database import Database
import discord
import discord.ext.commands as commands
import dotenv
import gspread
import os


# Configuration
dotenv.load_dotenv(".secrets/.env")
GOOGLE_CREDENTIALS_FILE = ".secrets/google_credentials.json"
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

# Google Sheets "Database"
gs_client = gspread.service_account(GOOGLE_CREDENTIALS_FILE)
database = Database(gs_client)
manage_players = ManagePlayers(database)
manage_teams = ManageTeams(database)

# Discord Intents
intents = discord.Intents.default()
intents.messages = True
intents.members = True
intents.message_content = True

# Discord Bot
# bot = commands.Bot(command_prefix=".", intents=intents)
bot = commands.Bot(command_prefix=".", intents=discord.Intents.all())


@bot.event
async def on_ready():
    """Event triggered when the bot is ready."""
    synced = await bot.tree.sync()
    print(f"synced {len(synced)} command(s)")


#######################################################################################################################
###                                          Bot Commands Begin                                                     ###
###vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv###

#######################
### Player Commands ###
#######################


@bot.tree.command(name="eml_register_as_player")
async def bot_player_register(interaction: discord.Interaction, region: str):
    """Register to become a Player"""
    await manage_players.register_player(interaction, region)


@bot.tree.command(name="eml_player_lookup")
async def bot_player_lookup(
    interaction: discord.Interaction, player_name: str = None, discord_id: str = None
):
    """Lookup a Player by name or Discord ID"""
    await manage_players.get_player_details(interaction, player_name, discord_id)


#####################
### Team Commands ###
#####################


@bot.tree.command(name="eml_create_team")
async def bot_team_register(interaction: discord.Interaction, team_name: str):
    """Create a new Team"""
    await manage_teams.register_team(interaction=interaction, team_name=team_name)


@bot.tree.command(name="eml_add_player")
async def bot_team_add_player(interaction: discord.Interaction, player_name: str):
    """Add a new player to your Team"""
    await manage_teams.add_player_to_team(interaction, player_name)


@bot.tree.command(name="eml_team_lookup")
async def bot_team_lookup(interaction: discord.Interaction, team_name: str):
    """Lookup a Team by name"""
    await manage_teams.get_team_details(interaction, team_name)


###^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^###
###                                          Bot Commands End                                                       ###
#######################################################################################################################


### Run Bot ###
bot.run(DISCORD_TOKEN)
