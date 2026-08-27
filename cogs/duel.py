import discord
from discord.ext import commands
import random

AUTHOR_SIGNATURE = "\n\n_— تم الصناعة بواسطة سيدريك 🪄_"

ALL_SPELLS = {
    # الهجومية (تسبب ضرر)
    "expelliarmus": {"name": "Expelliarmus", "display": "🪄 نزع السلاح (8 MP)", "mana_cost": 8, "damage": 20, "fail_chance": 10, "type": "هجوم"},
    "stupefy": {"name": "Stupefy", "display": "⚡ تخدير سحري (15 MP)", "mana_cost": 15, "damage": 35, "fail_chance": 20, "type": "هجوم"},
    "confringo": {"name": "Confringo", "display": "💥 لعنة الانفجار (22 MP)", "mana_cost": 22, "damage": 45, "fail_chance": 25, "type": "هجوم"},
    "reducto": {"name": "Reducto", "display": "🔨 تعويذة التفتيت (18 MP)", "mana_cost": 18, "damage": 38, "fail_chance": 22, "type": "هجوم"},
    "depulso": {"name": "Depulso", "display": "💨 تعويذة الإبعاد (10 MP)", "mana_cost": 10, "damage": 25, "fail_chance": 12, "type": "هجوم"},
    "bombarda": {"name": "Bombarda", "display": "💣 تفجير كبرى (30 MP)", "mana_cost": 30, "damage": 60, "fail_chance": 35, "type": "هجوم"},
    "incendio": {"name": "Incendio", "display": "🔥 كرة نار حارقة (16 MP)", "mana_cost": 16, "damage": 33, "fail_chance": 18, "type": "هجوم"},
    "flipendo": {"name": "Flipendo", "display": "🌀 صدمة ارتدادية (12 MP)", "mana_cost": 12, "damage": 22, "fail_chance": 14, "type": "هجوم"},

    # الدفاعية (تمنح درعاً مستقلاً يحمي الـ HP، وتربك تعويذة الخصم)
    "protego": {"name": "Protego", "display": "🛡️ درع حماية (+15 درع)", "mana_cost": 10, "shield": 15, "fail_chance": 8, "penalty_to_enemy": 15, "type": "دفاع"},
    "salvio": {"name": "Salvio Hexia", "display": "🛡️ حاجز الحماية (+25 درع)", "mana_cost": 18, "shield": 25, "fail_chance": 12, "penalty_to_enemy": 25, "type": "دفاع"},
    
    # العلاجية (تزيد نقاط الصحة HP فقط)
    "episkey": {"name": "Episkey", "display": "💚 شفاء خفيف (+20 HP)", "mana_cost": 15, "heal": 20, "fail_chance": 10, "type": "علاج"},
    "vulnera": {"name": "Vulnera Sanentur", "display": "✨ شفاء عميق (+35 HP)", "mana_cost": 25, "heal": 35, "fail_chance": 16, "type": "علاج"},

    # الشلل والحركة
    "petrificus": {"name": "Petrificus Totalus", "display": "❄️ الشلل التام (20 MP)", "mana_cost": 20, "damage": 30, "fail_chance": 22, "type": "شلل"},
    "immobulus": {"name": "Immobulus", "display": "🛑 تجميد الحركة (14 MP)", "mana_cost": 14, "damage": 24, "fail_chance": 15, "type": "شلل"}
}

class SpellSelectionView(discord.ui.View):
    def __init__(self, duel_session):
        super().__init__(timeout=45)
        self.duel_session = duel_session
        
        selected_keys = random.sample(list(ALL_SPELLS.keys()), 6)
        
        for key in selected_keys:
            spell = ALL_SPELLS[key]
            if "shield" in spell:
                style = discord.ButtonStyle.secondary  # رمادي/محايد للدفاع
            elif "heal" in spell:
                style = discord.ButtonStyle.success    # أخضر للعلاج
            else:
                style = discord.ButtonStyle.primary    # أزرق للهجوم
                
            self.add_item(SpellButton(key, spell, style))

class SpellButton(discord.ui.Button):
    def __init__(self, spell_key, spell_data, style):
        super().__init__(label=spell_data["display"], style=style)
        self.spell_key = spell_key
        self.spell_data = spell_data

    async def callback(self, interaction: discord.Interaction):
        session = self.view.duel_session
        user_id = interaction.user.id

        if user_id not in [session.p1.id, session.p2.id]:
            await interaction.response.send_message("❌ أنت لست مشاركاً في هذه المعركة!", ephemeral=True)
            return

        p_data = session.p1_data if user_id == session.p1.id else session.p2_data

        if p_data["mp"] < self.spell_data["mana_cost"]:
            await interaction.response.send_message(f"⚠️ ليس لديك مانا كافية لتنفيذ {self.spell_data['name']}! (تحتاج {self.spell_data['mana_cost']} MP)", ephemeral=True)
            return

        if user_id == session.p1.id:
            if session.p1_choice:
                await interaction.response.send_message("⚠️ لقد اخترت تعويذتك بالفعل، انتظر خصمك!", ephemeral=True)
                return
            session.p1_choice = self.spell_key
        else:
            if session.p2_choice:
                await interaction.response.send_message("⚠️ لقد اخترت تعويذتك بالفعل، انتظر خصمك!", ephemeral=True)
                return
            session.p2_choice = self.spell_key

        await interaction.response.send_message(f"✨ اخترت **{self.spell_data['name']}** بنجاح! بانتظار الخصم...", ephemeral=True)

        if session.p1_choice and session.p2_choice:
            self.view.stop()
            await session.execute_round(interaction)

class DuelSession:
    def __init__(self, ctx, p1, p2):
        self.ctx = ctx
        self.p1 = p1
        self.p2 = p2
        # إحصائيات اللاعبين: الصحة 200، المانا 40، الدرع يبدأ من 0
        self.p1_data = {"hp": 200, "mp": 40, "shield": 0}
        self.p2_data = {"hp": 200, "mp": 40, "shield": 0}
        self.p1_choice = None
        self.p2_choice = None
        self.round_num = 1
        self.message = None

    async def start_duel(self):
        embed = discord.Embed(
            title="⚡ مبارزة العصي الكبرى - نظام الدروع المستقلة",
            description=f"المواجهة الملحمية بين:\n🧙‍♂️ **{self.p1.mention}** ضد 🧙‍♂️ **{self.p2.mention}**\n\nاختر من قائمة التعويذات أدناه:",
            color=discord.Color.dark_purple()
        )
        embed.add_field(name=f"حالة {self.p1.name}", value="❤️ HP: 200/200\n🛡️ الدرع: 0\n🔮 MP: 40/40", inline=True)
        embed.add_field(name=f"حالة {self.p2.name}", value="❤️ HP: 200/200\n🛡️ الدرع: 0\n🔮 MP: 40/40", inline=True)
        embed.set_footer(text=f"— الجولة رقم {self.round_num} | {AUTHOR_SIGNATURE}")

        view = SpellSelectionView(self)
        self.message = await self.ctx.send(embed=embed, view=view)

    async def execute_round(self, interaction: discord.Interaction):
        # منح +7 مانا لكل لاعب في بداية الجولة
        self.p1_data["mp"] = min(40, self.p1_data["mp"] + 7)
        self.p2_data["mp"] = min(40, self.p2_data["mp"] + 7)

        s1 = ALL_SPELLS[self.p1_choice]
        s2 = ALL_SPELLS[self.p2_choice]

        self.p1_data["mp"] -= s1["mana_cost"]
        self.p2_data["mp"] -= s2["mana_cost"]

        # حساب نسب الفشل الأساسية مع تأثير الدروع على الخصم
        p1_fail_chance = s1["fail_chance"]
        p2_fail_chance = s2["fail_chance"]

        if "shield" in s2: # درع اللاعب الثاني يربك تعويذة الأول
            p1_fail_chance += s2.get("penalty_to_enemy", 0)
        if "shield" in s1: # درع اللاعب الأول يربك تعويذة الثاني
            p2_fail_chance += s1.get("penalty_to_enemy", 0)

        p1_fail = random.randint(1, 100) <= p1_fail_chance
        p2_fail = random.randint(1, 100) <= p2_fail_chance

        result_text = f"⚔️ **نتائج الجولة رقم {self.round_num}:**\n\n"

        # تخزين الأضرار والعلاجات لتطبيقها بالتزامن
        p1_action_msg = ""
        p2_action_msg = ""

        # معالجة اللاعب الأول
        if p1_fail:
            shield_msg = " بسبب تشويت درع الخصم!" if "shield" in s2 else ""
            p1_action_msg = f"❌ **{self.p1.name}**: تعويذة {s1['name']} فشلت{shield_msg}!\n"
        else:
            if "shield" in s1:
                sh_val = s1["shield"]
                self.p1_data["shield"] = sh_val  # تعيين قيمة الدرع الجديد
                p1_action_msg = f"🛡️ **{self.p1.name}** أنشأ درع حماية بقوة `{sh_val}` وارتبك الخصم!\n"
            elif "heal" in s1:
                heal_val = s1["heal"]
                self.p1_data["hp"] = min(200, self.p1_data["hp"] + heal_val)
                p1_action_msg = f"💚 **{self.p1.name}** ألقى تعويذة شفاء واستعاد `+{heal_val}` HP!\n"
            else:
                dmg = s1["damage"]
                # الهجوم يوجه للخصم (يأكل درعه أولاً ثم صحته)
                absorbed = min(self.p2_data["shield"], dmg)
                remaining_dmg = dmg - absorbed
                self.p2_data["shield"] -= absorbed
                self.p2_data["hp"] -= remaining_dmg
                p1_action_msg = f"🪄 **{self.p1.name}** ألقى {s1['name']} وأحدث ضرر `{dmg}` (تم امتصاص `{absorbed}` بالدرع، وباقي `{remaining_dmg}` على HP الخصم)!\n"

        # معالجة اللاعب الثاني
        if p2_fail:
            shield_msg = " بسبب تشويت درع الخصم!" if "shield" in s1 else ""
            p2_action_msg = f"❌ **{self.p2.name}**: تعويذة {s2['name']} فشلت{shield_msg}!\n\n"
        else:
            if "shield" in s2:
                sh_val = s2["shield"]
                self.p2_data["shield"] = sh_val
                p2_action_msg = f"🛡️ **{self.p2.name}** أنشأ درع حماية بقوة `{sh_val}` وارتبك الخصم!\n\n"
            elif "heal" in s2:
                heal_val = s2["heal"]
                self.p2_data["hp"] = min(200, self.p2_data["hp"] + heal_val)
                p2_action_msg = f"💚 **{self.p2.name}** ألقى تعويذة شفاء واستعاد `+{heal_val}` HP!\n\n"
            else:
                dmg = s2["damage"]
                absorbed = min(self.p1_data["shield"], dmg)
                remaining_dmg = dmg - absorbed
                self.p1_data["shield"] -= absorbed
                self.p1_data["hp"] -= remaining_dmg
                p2_action_msg = f"🪄 **{self.p2.name}** ألقى {s2['name']} وأحدث ضرر `{dmg}` (تم امتصاص `{absorbed}` بالدرع، وباقي `{remaining_dmg}` على HP الخصم)!\n\n"

        result_text += p1_action_msg + p2_action_msg

        # ضمان حدود الصحة بين 0 و 200
        self.p1_data["hp"] = max(0, min(200, self.p1_data["hp"]))
        self.p2_data["hp"] = max(0, min(200, self.p2_data["hp"]))
        self.p1_data["shield"] = max(0, self.p1_data["shield"])
        self.p2_data["shield"] = max(0, self.p2_data["shield"])

        result_text += f"📊 **الحالة بعد الجولة {self.round_num}:**\n"
        result_text += f"🧙‍♂️ **{self.p1.name}**: ❤️ HP `{self.p1_data['hp']}/200` | 🛡️ الدرع: `{self.p1_data['shield']}` | 🔮 MP `{self.p1_data['mp']}/40`\n"
        result_text += f"🧙‍♂️ **{self.p2.name}**: ❤️ HP `{self.p2_data['hp']}/200` | 🛡️ الدرع: `{self.p2_data['shield']}` | 🔮 MP `{self.p2_data['mp']}/40`\n"

        # فحص انتهاء المعركة
        if self.p1_data["hp"] == 0 or self.p2_data["hp"] == 0:
            if self.p1_data["hp"] > self.p2_data["hp"]:
                winner = self.p1
            elif self.p2_data["hp"] > self.p1_data["hp"]:
                winner = self.p2
            else:
                winner = None

            embed = discord.Embed(
                title="🏆 نهاية معركة العصي السحرية الكبرى!",
                description=result_text,
                color=discord.Color.gold()
            )
            if winner:
                embed.add_field(name="👑 بطل الحلبة المنتصر", value=f"الساحر الأسطوري **{winner.mention}** حسم المعركة بجدارة!", inline=False)
            else:
                embed.add_field(name="🤝 تعادل بطولي", value="انتهت المعركة بتساوي الطاقات بين السحرة!", inline=False)
            
            embed.set_footer(text=AUTHOR_SIGNATURE)
            await interaction.response.edit_message(content=None, embed=embed, view=None)
            return

        # الانتقال للجولة التالية
        self.round_num += 1
        self.p1_choice = None
        self.p2_choice = None

        embed = discord.Embed(
            title=f"⚔️ ملحمة هوجوورتس - الجولة {self.round_num}",
            description=result_text + "\n🔄 **بدأت الجولة التالية! حصل كلا اللاعبين على +7 MP. اختر من قائمة التعويذات العشوائية الجديدة:**",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=AUTHOR_SIGNATURE)

        view = SpellSelectionView(self)
        await interaction.response.edit_message(content=None, embed=embed, view=view)

class DuelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="مبارزة")
    async def duel_command(self, ctx, member: discord.Member = None):
        if not member:
            await ctx.send(f"⚠️ **يجب عليك عمل منشن للساحر الذي تريد مبارزته!**\nمثال: `!مبارزة @اسم_الشخص`{AUTHOR_SIGNATURE}")
            return
        
        if member.id == ctx.author.id:
            await ctx.send(f"⚠️ **لا يمكنك مبارزة نفسك يا أسطورة!**{AUTHOR_SIGNATURE}")
            return

        if member.bot:
            await ctx.send(f"⚠️ **الآليون لا يشاركون في مبارزات العصي، اختر ساحراً حقيقياً!**{AUTHOR_SIGNATURE}")
            return

        session = DuelSession(ctx, ctx.author, member)
        await session.start_duel()

async def setup(bot):
    await bot.add_cog(DuelCog(bot))
