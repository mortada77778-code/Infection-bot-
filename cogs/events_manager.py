import discord
from discord.ext import commands
import os
import json

AUTHOR_SIGNATURE = "\n\n_— تم الصناعة بواسطة سيدريك 🪄_"
EVENTS_FILE = "gaming_events.json"

def load_events():
    if not os.path.exists(EVENTS_FILE):
        return []
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_events(events):
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=4)

class EventModal(discord.ui.Modal, title="تسجيل فعالية جديدة لقسم الألعاب"):
    event_name = discord.ui.TextInput(
        label="اسم الفعالية",
        placeholder="مثال: تحدي التعاويذ الكبرى",
        required=True,
        max_length=100
    )
    referees = discord.ui.TextInput(
        label="الحُكّام",
        placeholder="مثال: RIDE, Cedric",
        required=True,
        max_length=100
    )
    winners = discord.ui.TextInput(
        label="الفائزين",
        placeholder="مثال: الفريق الأول / الساحر فلان",
        required=True,
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        presenter = interaction.user.name
        event_data = {
            "name": self.event_name.value,
            "referees": self.referees.value,
            "winners": self.winners.value,
            "presenter": presenter
        }

        events = load_events()
        events.append(event_data)
        save_events(events)

        await interaction.response.send_message(
            f"✅ **تم تسجيل الفعالية بنجاح في أرشيف القسم!**\n📌 الاسم: **{self.event_name.value}**{AUTHOR_SIGNATURE}",
            ephemeral=True
        )

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="تسجيل_فعالية")
    async def record_event(self, ctx):
        try:
            await ctx.message.delete()
        except:
            pass
            
        view = discord.ui.View()
        button = discord.ui.Button(label="اضغط هنا لملء بيانات الفعالية 📋", style=discord.ButtonStyle.green)
        
        async def button_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(EventModal())

        button.callback = button_callback
        view.add_item(button)
        
        await ctx.send(f"🎮 **[ لوحة تسجيل فعاليات قسم الألعاب ]**\nاضغط على الزر أدناه لتعبئة بيانات الفعالية:", view=view)

    @commands.command(name="الفعاليات")
    async def show_events(self, ctx):
        events = load_events()
        if not events:
            await ctx.send(f"⚠️ **لا توجد أي فعاليات مسجلة في الأرشيف حتى الآن!**{AUTHOR_SIGNATURE}")
            return

        embed = discord.Embed(
            title="📋 سجل فعاليات قسم الألعاب السحرية",
            description="إليك قائمة بجميع الفعاليات التي تم تسجيلها:",
            color=discord.Color.dark_purple()
        )

        for i, ev in enumerate(events, 1):
            details = (
                f"📌 **اسم الفعالية:** {ev['name']}\n"
                f"⚖️ **الحكم:** {ev['referees']}\n"
                f"🏆 **الفائزين:** {ev['winners']}\n"
                f"🎙️ **مقدم الفعالية:** {ev['presenter']}"
            )
            embed.add_field(name=f"فعالية رقم #{i}", value=details, inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(EventsCog(bot))
