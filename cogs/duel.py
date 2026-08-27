import discord
from discord.ext import commands
import random
import asyncio
import os
import json

AUTHOR_SIGNATURE = "— تم الصناعة بواسطة سيدريك 🪄"
LEADERBOARD_FILE = "duel_leaderboard.json"

def load_leaderboard():
    if not os.path.exists(LEADERBOARD_FILE):
        return {}
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_leaderboard(data):
    with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def add_win(user_id, username):
    db = load_leaderboard()
    uid = str(user_id)
    if uid not in db:
        db[uid] = {"name": username, "wins": 0}
    db[uid]["wins"] += 1
    db[uid]["name"] = username
    save_leaderboard(db)

SPELLS_DATABASE = {
    "expelliarmus": {"name": "Expelliarmus", "display": "🪄 Expelliarmus · 8 MP", "mana": 8, "damage": 20, "fail": 10, "type": "attack"},
    "stupefy": {"name": "Stupefy", "display": "⚡ Stupefy · 15 MP", "mana": 15, "damage": 35, "fail": 20, "type": "attack"},
    "confringo": {"name": "Confringo", "display": "💥 Confringo · 22 MP", "mana": 22, "damage": 45, "fail": 25, "type": "attack"},
    "reducto": {"name": "Reducto", "display": "🔨 Reducto · 18 MP", "mana": 18, "damage": 38, "fail": 22, "type": "attack"},
    "protego": {"name": "Protego", "display": "🛡️ Protego · 10 MP", "mana": 10, "shield": 15, "fail": 8, "type": "defense"},
    "episkey": {"name": "Episkey", "display": "💚 Episkey · 15 MP", "mana": 15, "heal": 20, "fail": 10, "type": "heal"},
    "incendio": {"name": "Incendio", "display": "🔥 Incendio · 16 MP", "mana": 16, "damage": 33, "fail": 18, "type": "attack"},
    "depulso": {"name": "Depulso", "display": "💨 Depulso · 10 MP", "mana": 10, "damage": 25, "fail": 12, "type": "attack"}
}

FLAVOR_MESSAGES = {
    "attack_hit": [
        "اشتعلت الشرارة من طرف العصا، ودوّى صوت اصطدام السحر بقوة!",
        "ارتجّت جدران القاعة من شدة العصف السحري!",
        "اندفعت طاقة مرعبة نحو الهدف دون أن يمتلك فرصة للهروب!",
        "تطاير الغبار من الحجارة إثر صدمة التعويذة المباشرة!"
    ],
    "shield_up": [
        "توهجت الأطراف بنور فضي خافت، وتشكل جدار من الطاقة الصلبة حول الساحر!",
        "التفَّ درع واقٍ محكم حول الساحر ليمتص صدمة القادم!",
        "انعكست أضواء التعويذات على حاجز سحري مانع لا يُقهر!"
    ],
    "heal_magic": [
        "تسلل دفء سحري غامض ليعيد ترتيب طاقات الجسد المنهك!",
        "لمع نور أخضر هادئ يداوي آثار الضربات العنيفة!",
        "تدفقت طاقة متجددة في عروق الساحر لتنعش حماسه!"
    ],
    "spell_fail": [
        "تطاير شرار خافت وفشلت التعويذة في مغادرة طرف العصا!",
        "تشتت التركيز للحظة عابرة فأجهضت التعويذة في مهدها!",
        "تردد صدى ضعيف وامتص الهواء طاقة التعويذة بلا أثر!"
    ]
}

class SpellSelectionView(discord.ui.View):
    def __init__(self, duel_session):
        super().__init__(timeout=60)
        self.duel_session = duel_session
        
        keys = random.sample(list(SPELLS_DATABASE.keys()), 6)
        for k in keys:
            spell = SPELLS_DATABASE[k]
            self.add_item(SpellButton(k, spell))

class SpellButton(discord.ui.Button):
    def __init__(self, key, spell):
        super().__init__(label=spell["display"], style=discord.ButtonStyle.secondary)
        self.spell_key = key
        self.spell_data = spell

    async def callback(self, interaction: discord.Interaction):
        session = self.view.duel_session
        user_id = interaction.user.id

        if user_id not in [session.p1.id, session.p2.id]:
            await interaction.response.send_message("❌ هذه القاعة ليست مخصصة لك.", ephemeral=True)
            return

        p_data = session.p1_data if user_id == session.p1.id else session.p2_data

        if p_data["mp"] < self.spell_data["mana"]:
            await interaction.response.send_message("⚠️ رصيد المانا غير كافٍ لإنشاء هذه التعويذة.", ephemeral=True)
            return

        if user_id == session.p1.id:
            if session.p1_choice:
                await interaction.response.send_message("✓ لقد اخترت تعويذتك مسبقاً لهذه الجولة.", ephemeral=True)
                return
            session.p1_choice = self.spell_key
        else:
            if session.p2_choice:
                await interaction.response.send_message("✓ لقد اخترت تعويذتك مسبقاً لهذه الجولة.", ephemeral=True)
                return
            session.p2_choice = self.spell_key

        await interaction.response.send_message("✓ تم اختيار التعويذة", ephemeral=True)
        await session.update_status_message()

        if session.p1_choice and session.p2_choice:
            self.view.stop()
            await session.execute_round(interaction)

class DuelSession:
    def __init__(self, ctx, p1, p2):
        self.ctx = ctx
        self.p1 = p1
        self.p2 = p2
        self.p1_data = {"hp": 200, "mp": 40, "shield": 0}
        self.p2_data = {"hp": 200, "mp": 40, "shield": 0}
        self.p1_choice = None
        self.p2_choice = None
        self.round_num = 1
        self.message = None

    async def start_duel(self):
        embed = self.build_main_embed("✨ اختر تعويذتك")
        view = SpellSelectionView(self)
        self.message = await self.ctx.send(embed=embed, view=view)

    def build_main_embed(self, status_text):
        embed = discord.Embed(
            title="⚔️ مبارزة العصي السحرية",
            description=f"**الجولة {self.round_num:02d}**\n\n"
                        f"🧙‍♂️ {self.p1.name}   ❤️ {self.p1_data['hp']}   🔮 {self.p1_data['mp']}\n"
                        f"VS\n"
                        f"🧙‍♂️ {self.p2.name}   ❤️ {self.p2_data['hp']}   🔮 {self.p2_data['mp']}\n\n"
                        f"──────────────────\n"
                        f"{status_text}",
            color=0x2b1338
        )
        embed.set_footer(text=AUTHOR_SIGNATURE)
        return embed

    async def update_status_message(self):
        p1_status = "✓ تم الاختيار" if self.p1_choice else "⏳ يختار..."
        p2_status = "✓ تم الاختيار" if self.p2_choice else "⏳ يختار..."
        text = f"حالة الخصوم:\n{self.p1.name}: {p1_status}  |  {self.p2.name}: {p2_status}"
        embed = self.build_main_embed(text)
        try:
            await self.message.edit(embed=embed)
        except:
            pass

    async def execute_round(self, interaction: discord.Interaction):
        self.p1_data["mp"] = min(40, self.p1_data["mp"] + 7)
        self.p2_data["mp"] = min(40, self.p2_data["mp"] + 7)

        s1 = SPELLS_DATABASE[self.p1_choice]
        s2 = SPELLS_DATABASE[self.p2_choice]

        self.p1_data["mp"] -= s1["mana"]
        self.p2_data["mp"] -= s2["mana"]

        p1_fail = random.randint(1, 100) <= s1["fail"]
        p2_fail = random.randint(1, 100) <= s2["fail"]

        p1_result_line = ""
        p2_result_line = ""
        flavor_picks = []

        if p1_fail:
            p1_result_line = f"{s1['name']} فشلت — لم تسبب ضررًا"
            flavor_picks.append(random.choice(FLAVOR_MESSAGES["spell_fail"]))
        else:
            if s1["type"] == "attack":
                dmg = s1["damage"]
                absorbed = min(self.p2_data["shield"], dmg)
                rem = dmg - absorbed
                self.p2_data["shield"] -= absorbed
                self.p2_data["hp"] -= rem
                p1_result_line = f"{s1['name']} نجحت — {dmg} ضرر"
                flavor_picks.append(random.choice(FLAVOR_MESSAGES["attack_hit"]))
            elif s1["type"] == "defense":
                self.p1_data["shield"] = s1["shield"]
                p1_result_line = f"{s1['name']} نجحت — درع بقوة {s1['shield']}"
                flavor_picks.append(random.choice(FLAVOR_MESSAGES["shield_up"]))
            elif s1["type"] == "heal":
                self.p1_data["hp"] = min(200, self.p1_data["hp"] + s1["heal"])
                p1_result_line = f"{s1['name']} نجحت — شفاء +{s1['heal']} HP"
                flavor_picks.append(random.choice(FLAVOR_MESSAGES["heal_magic"]))

        if p2_fail:
            p2_result_line = f"{s2['name']} فشلت — لم تسبب ضررًا"
            flavor_picks.append(random.choice(FLAVOR_MESSAGES["spell_fail"]))
        else:
            if s2["type"] == "attack":
                dmg = s2["damage"]
                absorbed = min(self.p1_data["shield"], dmg)
                rem = dmg - absorbed
                self.p1_data["shield"] -= absorbed
                self.p1_data["hp"] -= rem
                p2_result_line = f"{s2['name']} نجحت — {dmg} ضرر"
                flavor_picks.append(random.choice(FLAVOR_MESSAGES["attack_hit"]))
            elif s2["type"] == "defense":
                self.p2_data["shield"] = s2["shield"]
                p2_result_line = f"{s2['name']} نجحت — درع بقوة {s2['shield']}"
                flavor_picks.append(random.choice(FLAVOR_MESSAGES["shield_up"]))
            elif s2["type"] == "heal":
                self.p2_data["hp"] = min(200, self.p2_data["hp"] + s2["heal"])
                p2_result_line = f"{s2['name']} نجحت — شفاء +{s2['heal']} HP"
                flavor_picks.append(random.choice(FLAVOR_MESSAGES["heal_magic"]))

        self.p1_data["hp"] = max(0, min(200, self.p1_data["hp"]))
        self.p2_data["hp"] = max(0, min(200, self.p2_data["hp"]))
        self.p1_data["shield"] = max(0, self.p1_data["shield"])
        self.p2_data["shield"] = max(0, self.p2_data["shield"])

        active_flavor = random.choice(flavor_picks) if flavor_picks else "تردد صدى التعويذات في أرجاء القاعة."

        result_desc = (
            f"**⚔️ الجولة {self.round_num:02d}**\n\n"
            f"🧙‍♂️ {self.p1.name}\n"
            f"🪄 {s1['name']}\n\n"
            f"VS\n\n"
            f"🧙‍♂️ {self.p2.name}\n"
            f"🔥 {s2['name']}\n\n"
            f"💬 *\"{active_flavor}\"*\n\n"
            f"✨ **النتيجة**\n"
            f"• {self.p1.name}: {p1_result_line}\n"
            f"• {self.p2.name}: {p2_result_line}\n\n"
            f"──────────────────\n"
            f"❤️ {self.p1.name} {self.p1_data['hp']}/200\n"
            f"❤️ {self.p2.name} {self.p2_data['hp']}/200\n\n"
            f"🔮 المانا تتجدد +7 في بداية الجولة التالية"
        )

        embed = discord.Embed(
            title="⚡ كشف التعويذات",
            description=result_desc,
            color=0xd4af37
        )
        embed.set_footer(text=AUTHOR_SIGNATURE)

        if self.p1_data["hp"] == 0 or self.p2_data["hp"] == 0:
            winner = self.p1 if self.p1_data["hp"] > self.p2_data["hp"] else self.p2
            add_win(winner.id, winner.name)
            
            embed.title = "🏆 حسمت المعركة السحرية"
            embed.description += f"\n\n👑 **بطل الحلبة:** {winner.mention}\n*(تم تسجيل الفوز في لوحة صدارة المبارزات)*"
            await interaction.response.edit_message(content=None, embed=embed, view=None)
            return

        self.round_num += 1
        self.p1_choice = None
        self.p2_choice = None

        await interaction.response.edit_message(content=None, embed=embed, view=None)
        
        await asyncio.sleep(4)
        
        next_embed = self.build_main_embed("✨ اختر تعويذتك")
        next_view = SpellSelectionView(self)
        self.message = await self.ctx.send(embed=next_embed, view=next_view)

class DuelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="مبارزة")
    async def duel_command(self, ctx, member: discord.Member = None):
        if not member:
            await ctx.send("⚠️ يرجى عمل منشن للساحر المراد مبارزته: `!مبارزة @اسم_الشخص`", delete_after=10)
            return
        if member.id == ctx.author.id:
            await ctx.send("⚠️ لا يمكنك مبارزة نفسك.", delete_after=10)
            return
        if member.bot:
            await ctx.send("⚠️ البوتات لا تشارك في مبارزات العصي.", delete_after=10)
            return

        session = DuelSession(ctx, ctx.author, member)
        await session.start_duel()

    @commands.command(name="صدارة-المبارزات")
    async def leaderboard_command(self, ctx):
        db = load_leaderboard()
        if not db:
            await ctx.send("⚠️ لا توجد أي انتصارات مسجلة في سجل المبارزات حتى الآن.")
            return

        sorted_players = sorted(db.values(), key=lambda x: x["wins"], reverse=True)[:10]

        desc = "🏆 **قائمة أبطال حلبة السحر:**\n\n"
        for idx, player in enumerate(sorted_players, 1):
            medal = "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else f"#{idx}"))
            desc += f"{medal} **{player['name']}** ── 🎯 `{player['wins']}` انتصار\n"

        embed = discord.Embed(
            title="📜 لوحة صدارة المبارزات",
            description=desc,
            color=0xd4af37
        )
        embed.set_footer(text=AUTHOR_SIGNATURE)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(DuelCog(bot))
