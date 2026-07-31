import disnake

class MusicControlView(disnake.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)  # Persistent View
        self.player = player

    def _get_target_pipeline(self, interaction: disnake.MessageInteraction):
        if interaction.author.voice and interaction.author.voice.channel:
            pipeline = self.player.get_pipeline(interaction.author.voice.channel.id)
            if pipeline:
                return pipeline
        return self.player.primary_pipeline

    @disnake.ui.button(label="Pause / Resume", style=disnake.ButtonStyle.primary, emoji="⏯️", custom_id="shanty_pause_resume")
    async def toggle_pause(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        pipeline = self._get_target_pipeline(interaction)

        if not pipeline.voice_client or not pipeline.voice_client.is_connected():
            await interaction.response.send_message("Not connected to a voice channel.", ephemeral=True)
            return

        if pipeline.is_paused:
            await pipeline.resume()
            await interaction.response.send_message("Resumed playback!", ephemeral=True)
        elif pipeline.voice_client and (pipeline.voice_client.is_playing() or pipeline.current_track):
            await pipeline.pause()
            await interaction.response.send_message("Paused playback.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is currently playing.", ephemeral=True)

    @disnake.ui.button(label="Skip", style=disnake.ButtonStyle.secondary, emoji="⏭️", custom_id="shanty_skip")
    async def skip_track(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        pipeline = self._get_target_pipeline(interaction)

        if pipeline.voice_client and (pipeline.voice_client.is_playing() or pipeline.voice_client.is_paused()):
            await pipeline.skip()
            await interaction.response.send_message("Skipped track!", ephemeral=True)
        else:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)
