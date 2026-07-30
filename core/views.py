import disnake

class MusicControlView(disnake.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)  # Persistent View
        self.player = player

    @disnake.ui.button(label="Pause / Resume", style=disnake.ButtonStyle.primary, emoji="⏯️", custom_id="shantybot:pause")
    async def toggle_pause(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if not self.player.voice_client:
            await interaction.response.send_message("Not connected to a voice channel.", ephemeral=True)
            return

        if self.player.voice_client.is_paused():
            self.player.voice_client.resume()
            await interaction.response.send_message("Resumed playback!", ephemeral=True)
        elif self.player.voice_client.is_playing():
            self.player.voice_client.pause()
            await interaction.response.send_message("Paused playback.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is currently playing.", ephemeral=True)

    @disnake.ui.button(label="Skip", style=disnake.ButtonStyle.secondary, emoji="⏭️", custom_id="shantybot:skip")
    async def skip_track(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if self.player.voice_client and (self.player.voice_client.is_playing() or self.player.voice_client.is_paused()):
            self.player.voice_client.stop()
            await interaction.response.send_message("Skipped track!", ephemeral=True)
        else:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)

    @disnake.ui.button(label="Raid Party!", style=disnake.ButtonStyle.danger, emoji="🏴‍☠️", custom_id="shantybot:raid")
    async def trigger_raid(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.author.voice:
            await interaction.followup.send("Join a voice channel to summon the raiding party!", ephemeral=True)
            return
        
        success = await self.player.trigger_raid(interaction.author.voice.channel)
        if success:
            await interaction.followup.send("🏴‍☠️ **RAIDING PARTY!** Batten down the hatches!", ephemeral=False)
        else:
            await interaction.followup.send("No raid sound files found in ship's hold!", ephemeral=True)
