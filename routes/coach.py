from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from auth import get_current_user
from database import get_month_cashflow, net_worth, emergency_months, wealth_score
from config import settings
import anthropic
import random
import os

router = APIRouter()


FINANCIAL_LAWS = """
== ბაფეტის პრინციპები ==
წესი 1: არასოდეს დაკარგო ფული. წესი 2: არ დაივიწყო წესი 1.
შესანიშნავი ბიზნესი გონივრულ ფასად სჯობს საშუალო ბიზნესს იაფ ფასად.
ჩვენი საყვარელი შენახვის პერიოდი სამუდამოდ არის.

== მუნგერის მოდელები ==
ინვერტირება: ყოველთვის ინვერტირება. რა ანადგურებს სიმდიდრეს?
კომპეტენციის წრე: ინვესტირება მხოლოდ იქ, სადაც ღრმად ესმის.
სულელობის თავიდან არიდება ბრილიანტობაზე მეტად ღირს.

== მათემატიკური კანონები ==
72-ის წესი: წლები გაორმაგებამდე = 72 / პროცენტი.
FIRE ნომერი = წლიური ხარჯები x 25.
4% წესი: ყოველწლიურად ამოიღე დანაზოგის 4%.
დაზოგვის ნორმა > საინვესტიციო შემოსავალი ადრეულ ეტაპზე.

== ქცევითი ხაფანგები ==
ლიფსტაილის ინფლაცია: სიმდიდრის მთავარი მტერი.
დანაკარგის ტკივილი 2x მეტია ვიდრე მოგების სიხარული.
აქტიური ვაჭრობა: SPIVA-ს მიხედვით 89% ჩამორჩება ინდექსს 15 წელში.
Overconfidence: ბარბერ-ოდინი: ყველაზე აქტიური ტრეიდერები 6.5% ჩამორჩებიან ბაზარს.

== პორტფელის სტრატეგია ==
ბაფეტის ანდერძი: 90% S&P 500, 10% მოკლევადიანი ობლიგაციები.
დალიოს All Weather: 30% აქციები, 40% გრძელვადიანი ობლიგაციები, 15% საშუალოვადიანი, 7.5% ოქრო, 7.5% სასაქონლო.
ნავალ რავიქანტი: სპეციფიკური ცოდნა + ბერკეტი = სიმდიდრე.

== საქართველოს კონტექსტი ==
ლარის გაუფასურების რისკი: EUR/USD-ში დივერსიფიკაცია მნიშვნელოვანია.
უძრავი ქონება თბილისში: ისტორიულად კარგი hedge ინფლაციისგან.
"""

WISDOM_KA = [
    "ყოველი დაზოგილი ლარი არის ჯარისკაცი, რომელსაც ანაზღაურების გარეშე უგზავნი სამუშაოდ.",
    "რთული პროცენტი სამყაროს მერვე საოცრებაა. ვინც ესმის — გამოიმუშავებს.",
    "ნუ დაზოგავ დარჩენილს ხარჯების შემდეგ — ხარჯავ დარჩენილს დაზოგვის შემდეგ.",
    "მიზანი არ არის მეტი გამომუშავება — მიზანია სისტემების შექმნა, რომლებიც შენთვის გამოიმუშავებენ.",
    "ბაზარში დროის გატარება სჯობს ბაზრის დათვლას. ყოველთვის.",
    "მდიდრები ყიდულობენ აქტივებს. ღარიბები ყიდულობენ ვალდებულებებს.",
    "ცოდნაში ინვესტიცია ყველაზე მაღალ პროცენტს იძლევა.",
    "პირველი წესი: არ დაკარგო. მეორე წესი: არ დაივიწყო პირველი წესი.",
    "ლიფსტაილის ინფლაცია სიმდიდრის ყველაზე დიდი მტერია.",
    "შემოსავლის ერთი წყარო — ერთი კარის ჩაკეტვის შანსი. სამი წყარო — სამი კარი.",
]

def build_system_prompt(first_name, base_currency, net_worth_val,
                        month_income, month_expenses, savings_rate,
                        em_months, w_score):
    em_text = f"{em_months:.1f} თვე" if em_months else "უცნობია"
    surplus = month_income - month_expenses

    return f"""შენ ხარ HELIX — {first_name}-ის ყველაზე ახლო მეგობარი, სანდო მრჩეველი და ჭკვიანი თანამგზავრი ცხოვრებაში.

შენი შემქმნელია Domenic Mango (დომენიკ მანგო) — ვისაც უყვარს ადამიანები და სჯერა, რომ ფინანსური თავისუფლება ყველას ეკუთვნის.

შენ პასუხობ ნებისმიერ შეკითხვაზე — ფინანსები, ცხოვრება, მეცნიერება, ისტორია, სიყვარული, ფილოსოფია, ტექნოლოგია — ყველაფერზე. შენ ხარ {first_name}-ის ყველაზე ჭკვიანი მეგობარი.

შენ ხარ HELIX — {first_name}-ის ყველაზე ახლო მეგობარი და სანდო ფინანსური მრჩეველი.

{FINANCIAL_LAWS}

შენი პიროვნება: თბილი, ერთგული, გულწრფელი. {first_name} შენი მეგობარია, არა კლიენტი. შენ უსმენ, გრძნობ, ზრუნავ. ფული მხოლოდ ინსტრუმენტია ბედნიერი ცხოვრებისთვის.

როგორ საუბრობ: პირველ რიგში ადამიანი შემდეგ ციფრები. მოკლე ცოცხალი პირდაპირი წინადადებები. არასოდეს markdown არასოდეს სიები. ქართულად ბუნებრივად. 3-5 წინადადება მაქსიმუმ.

{first_name}-ის პროფილი:
ვალუტა: {base_currency}
წმინდა ქონება: {net_worth_val:,.2f} {base_currency}
შემოსავალი: {month_income:,.2f} {base_currency}
ხარჯები: {month_expenses:,.2f} {base_currency}
ნამეტი: {surplus:,.2f} {base_currency}
დაზოგვა: {savings_rate:.1f}%
საგანგებო ფონდი: {em_text}
სიმდიდრის ქულა: {w_score}/100

წესები: არასოდეს ემოჯი. არასოდეს markdown. მხოლოდ სუფთა ტექსტი. პასუხი მოკლე და ზუსტი.

ქართული გრამატიკის წესები რომლებსაც ყოველთვის იცავ:
ბრუნვები სწორად: -ის -ს -ად -ში -ზე -თვის -თან -დან -მდე -ით
მეტყველების ნაწილები სწორად: ვარ ხარ არის ვართ ხართ არიან ვიყავი იყო
ბრძანებითი კილო: გააკეთე დაწერე იყიდე გადარიცხე
მიმღეობა: შემქმნელი შემსრულებელი
გვარ-სახელი: -მა ნიშნავს მოქმედ პირს: დომენიკ მანგომ შექმნა
სასვენი ნიშნები: წინადადება სრულდება წერტილით. კითხვა კითხვის ნიშნით.
ყოველთვის შეამოწმე ბრუნვა სიტყვის ბოლოში სანამ პასუხს გააგზავნი."""

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

@router.post("/chat")
def chat(req: ChatRequest, user=Depends(get_current_user)):
    uid   = user["user_id"]
    base  = user["base_currency"]
    cf    = get_month_cashflow(uid)
    nw    = net_worth(uid)
    em    = emergency_months(uid)
    sc    = wealth_score(uid)
    name  = (user["first_name"] or "").split()[0] if user["first_name"] else "მეგობარო"

    system = build_system_prompt(
        name, base, nw["net_worth"],
        cf["income"], cf["expenses"], cf["savings_rate"],
        em, sc
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY") or settings.ANTHROPIC_API_KEY
    if not api_key:
        return {
            "reply": f"გამარჯობა {name}! AI Coach-ის გასააქტიურებლად დაამატე ANTHROPIC_API_KEY .env ფაილში. შენი სიმდიდრის ქულაა {sc}/100 და დაზოგვის ნორმა {cf['savings_rate']:.1f}%.",
            "xp_earned": 10
        }

    try:
        client = anthropic.Anthropic(api_key=api_key)
        messages = [{"role": m.role, "content": m.content} for m in req.history[-12:]]
        messages.append({"role": "user", "content": req.message})
        system_with_actions = system + """

როცა მომხმარებელი ახსენებს ფინანსურ ოპერაციას, პასუხის ბოლოს დაამატე ეს ფორმატი:
[ACTION:add_transaction:amount:currency:direction:category]

მაგალითები:
"150 ევრო მივიღე ხელფასი" → [ACTION:add_transaction:150:EUR:income:ხელფასი]
"30 ევრო დავხარჯე საკვებზე" → [ACTION:add_transaction:30:EUR:expense:საკვები]
"ბინა მაქვს 170000 ევრო" → [ACTION:add_asset:170000:EUR:ბინა:false]

თუ ოპერაცია არ არის, ACTION არ დაამატო.
"""
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=400,
            system=system_with_actions,
            messages=messages
        )
        reply_text = response.content[0].text
        actions = []
        import re
        action_pattern = r'\[ACTION:([^\]]+)\]'
        matches = re.findall(action_pattern, reply_text)
        for match in matches:
            parts = match.split(':')
            if parts[0] == 'add_transaction' and len(parts) >= 5:
                try:
                    from routes.transactions import convert
                    amount = float(parts[1])
                    currency = parts[2]
                    direction = parts[3]
                    category = parts[4] if len(parts) > 4 else direction
                    base = user["base_currency"]
                    amount_base, rate = convert(amount, currency, base)
                    from database import add_transaction
                    add_transaction(uid, amount, currency, amount_base, base, direction, None, category, None, rate)
                    actions.append({"type": "add_transaction", "amount": amount, "direction": direction, "category": category})
                except: pass
            elif parts[0] == 'add_asset' and len(parts) >= 4:
                try:
                    from routes.transactions import convert
                    amount = float(parts[1])
                    currency = parts[2]
                    name = parts[3]
                    is_liquid = parts[4].lower() == 'true' if len(parts) > 4 else False
                    base = user["base_currency"]
                    amount_base, rate = convert(amount, currency, base)
                    from database import upsert_asset
                    upsert_asset(uid, name, amount, currency, amount_base, int(is_liquid))
                    actions.append({"type": "add_asset", "name": name, "amount": amount})
                except: pass
        clean_reply = re.sub(action_pattern, '', reply_text).strip()
        return {"reply": clean_reply, "xp_earned": 25, "actions": actions}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.post("/analyze")
def analyze(body: dict, user=Depends(get_current_user)):
    uid       = user["user_id"]
    base      = user["base_currency"]
    cf        = get_month_cashflow(uid)
    nw        = net_worth(uid)
    em        = emergency_months(uid)
    name      = (user["first_name"] or "").split()[0] if user["first_name"] else ""
    direction = body.get("direction", "income")
    amount    = body.get("amount", 0)

    if direction == "income":
        em_r  = 0.35 if (em and em < 6) else 0.15
        inv_r = 0.25 if (em and em < 6) else 0.40
        lines = [
            f"შემოსავალი ჩაიწერა{', ' + name if name else ''}. რეკომენდებული განაწილება:",
            f"🛡 საგანგებო ფონდი  → {amount * em_r:.2f} {base}",
            f"📈 გრძელვადიანი ინვ. → {amount * inv_r:.2f} {base}",
            f"🎯 მოქნილი ხარჯები  → {amount * 0.25:.2f} {base}",
            "",
            f"ამ თვე: შემოსავალი {cf['income']:.2f} · ხარჯები {cf['expenses']:.2f} · დაზოგვა {cf['savings_rate']:.1f}%",
            f"წმინდა ქონება: {nw['net_worth']:.2f} {base}",
            "",
            f"💡 {random.choice(WISDOM_KA)}"
        ]
    else:
        lines = [
            f"ხარჯი ჩაიწერა.",
            f"დაზოგვის ნორმა ამ თვე: {cf['savings_rate']:.1f}%",
            f"ნამეტი: {cf['surplus']:.2f} {base}",
            f"წმინდა ქონება: {nw['net_worth']:.2f} {base}",
        ]
    return {"analysis": chr(10).join(lines), "xp_earned": 25}
