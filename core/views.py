import disnake

class MusicControlView(disnake.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)  # Persistent View
        self.player = player

    @disnake.ui.button(label="Pause / Resume", style=disnake.ButtonStyle.primary, emoji="⏯️", custom_id="shanty_pause_resume")
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

    @disnake.ui.button(label="Skip", style=disnake.ButtonStyle.secondary, emoji="⏭️", custom_id="shanty_skip")
    async def skip_track(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if self.player.voice_client and (self.player.voice_client.is_playing() or self.player.voice_client.is_paused()):
            self.player.voice_client.stop()
            await interaction.response.send_message("Skipped track!", ephemeral=True)
        else:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)
