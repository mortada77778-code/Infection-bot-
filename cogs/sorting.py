import discord
from discord.ext import commands
import os
import json

AUTHOR_SIGNATURE = "\n\n_— تم الصناعة بواسطة سيدريك 🪄_"
DATA_FILE = "students_houses.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

QUESTIONS = [
    {
        "question": "🔮 **السؤال الأول:** أمامك مفترق طرق في غابة مظلمة، أين ستخطو بقدمك؟",
        "options": {
            "🔴 الطريق الضيق المليء بالشجيرات الحادة، لكنه يقود مباشرة للقمة.": "Gryffindor",
            "🟢 الطريق المخفي خلف الأشجار الملتوية، الذي يوفر لك حماية وسرية تامة.": "Slytherin",
            "🔵 الطريق المغطى بالرموز والطلاسم الغامضة التي تنتظر من يحلها.": "Ravenclaw",
            "🟡 الطريق الممهد والآمن الذي سلكه الآخرون لتصل مع الجميع سالماً.": "Hufflepuff"
        }
    }
]

class SortingView(discord.ui.View):
    def __init__(self, user_id, question_index=0, scores=None):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.question_index = question_index
        self.scores = scores or {"Gryffindor": 0, "Slytherin": 0, "Ravenclaw": 0, "Hufflepuff": 0}
        q_data = QUESTIONS[question_index]
        for text, house in q_data["options"].items():
            self.add_item(SortingButton(text, house))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("🎩 هذه القبعة ليست مخصصة لك!", ephemeral=True)
            return False
        return True

class SortingButton(discord.ui.Button):
    def __init__(self, label_text, house):
        super().__init__(label=label_text[:80], style=discord.ButtonStyle.secondary)
        self.house = house

    async def callback(self, interaction: discord.Interaction):
        view: SortingView = self.view
        view.scores[self.house] += 1
        
        final_house = max(view.scores, key=view.scores.get)
        data = load_data()
        data[str(interaction.user.id)] = {"name": interaction.user.name, "house": final_house}
        save_data(data)

        try:
            role = discord.utils.get(interaction.guild.roles, name=final_house)
            if role:
                await interaction.user.add_roles(role)
        except:
            pass

        await interaction.response.edit_message(content=f"🪄 تم تصنيفك في بيت: **{final_house}**!{AUTHOR_SIGNATURE}", view=None)

class SortingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="قباعة")
    async def sorting_hat_command(self, ctx):
        view = SortingView(ctx.author.id, 0)
        await ctx.send(f"🎩 **اختبار القبعة:**\n{QUESTIONS[0]['question']}{AUTHOR_SIGNATURE}", view=view)

async def setup(bot):
    await bot.add_cog(SortingCog(bot))

