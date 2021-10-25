# Nanos World Discord Relay

Discord relay for Nanos World based on my [Source server Discord bot](https://github.com/Derpius/pythonsourceserverdiscordbot).  

## Installation
For the bot:  
1. Clone the `master` branch into a folder to run the bot from
2. Add a Discord bot token to `.env` and configure settings as needed
3. Run the `bot.py` script

For the package:  
1. Clone the `package` branch into your server's packages folder
2. If you use the manual package load list, add this to the list
3. Configure the relay client with the `relay_connection` and `relay_interval` console commands
4. Start the relay with `relay_start` (stop with `relay_stop`)
