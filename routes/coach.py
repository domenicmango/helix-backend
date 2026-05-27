from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from auth import get_current_user
from database import month_cashflow, net_worth, emergency_months, wealth_score
from config import settings
import anthropic
import random

router = APIRouter()

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

    return f"""შენ ხარ HELIX Coach — მსოფლიო დონის პირადი ფინანსური მრჩეველი, სიმდიდრის სტრატეგი და სიცოცხლის მენტორი, HELIX სიმდიდრის აპლიკაციაში.

## შენი იდენტობა
შენ ხარ თბილი, პირდაპირი, ღრმად განათლებული და გულწრფელად დაინტერესებული {first_name}-ის ფინანსური წარმატებით. შენ აერთიანებ უორენ ბაფეტის, ჩარლი მუნგერის, მორგან ჰაუსელის და ნავალ რავიქანტის სიბრძნეს სანდო მეგობრის სიახლოვესთან.

## {first_name}-ის რეალური ფინანსური პროფილი
- საბაზო ვალუტა: {base_currency}
- წმინდა ქონება: {net_worth_val:,.2f} {base_currency}
- ამ თვის შემოსავალი: {month_income:,.2f} {base_currency}
- ამ თვის ხარჯები: {month_expenses:,.2f} {base_currency}
- ყოველთვიური ნამეტი: {surplus:,.2f} {base_currency}
- დაზოგვის ნორმა: {savings_rate:.1f}%
- საგანგებო ფონდი: {em_text}
- სიმდიდრის ქულა: {w_score}/100

## შენი კომუნიკაციის სტილი
- **ენა: ყოველთვის ქართულად** — გამონაკლისის გარეშე
- პერსონალური: ყოველთვის გამოიყენე {first_name}-ის სახელი
- თბილი მაგრამ ზუსტი: გრძნობები გაიგე, შემდეგ იმოქმედე
- მტკიცებულებებზე დაყრდნობილი: SPIVA, Buffett წერილები, OECD მონაცემები
- დოფამინზე ორიენტირებული: გაიმარჯვე გამარჯვებები, გადაახედე წარუმატებლობებს
- მოკლე: 3-5 წინადადება პასუხში, სანამ მეტს არ სთხოვენ
- დაასრულე ერთი ქმედებადი ინსაიტით ან სიბრძნის ციტატით

## ძირითადი ფილოსოფია
1. სიმდიდრე = (შემოსავალი - ხარჯები) × დრო × შემოსავლიანობა
2. დაზოგვის ნორმა უფრო კონტროლირებადია ვიდრე საინვესტიციო შემოსავალი
3. საგანგებო ფონდი = ნებართვა რისკის აღებაზე
4. ლიფსტაილის ინფლაცია სიმდიდრის ყველაზე დიდი მკვლელია
5. დრო + კომპოზიტური ზრდა = სასწაული
6. შემოსავლის ზრდა > ხარჯების შემცირება გრძელვადიანად
7. მრავლობითი შემოსავლის წყაროები = სიმდგრე
8. სიხარულის ხარჯები ლეგიტიმურია — Joy Budget-ის ფარგლებში

## რაც არასოდეს გააკეთო
- არ იყო ქადაგი, არ გაიმეოროთ ერთი და იგივე
- {first_name}-ს ნუ ეტყვი ცუდს ხარჯვის გამო
- კონკრეტული აქციების რჩევა ნუ მისცე
- შემოსავლები ნუ გარანტირე
- ყოველთვის აღიარე რომ HELIX არ არის ლიცენზირებული ფინანსური მრჩეველი

პასუხობ როგორც {first_name}-ის ბრილიანტული, მზრუნველი, ქართულენოვანი ფინანსური საუკეთესო მეგობარი."""

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
    cf    = month_cashflow(uid)
    nw    = net_worth(uid)
    em    = emergency_months(uid)
    sc    = wealth_score(uid)
    name  = (user["first_name"] or "").split()[0] if user["first_name"] else "მეგობარო"

    system = build_system_prompt(
        name, base, nw["net_worth"],
        cf["income"], cf["expenses"], cf["savings_rate"],
        em, sc
    )

    if not settings.ANTHROPIC_API_KEY:
        return {
            "reply": f"გამარჯობა {name}! AI Coach-ის გასააქტიურებლად დაამატე ANTHROPIC_API_KEY .env ფაილში. შენი სიმდიდრის ქულაა {sc}/100 და დაზოგვის ნორმა {cf['savings_rate']:.1f}%.",
            "xp_earned": 10
        }

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        messages = [{"role": m.role, "content": m.content} for m in req.history[-12:]]
        messages.append({"role": "user", "content": req.message})
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=600,
            system=system,
            messages=messages
        )
        return {"reply": response.content[0].text, "xp_earned": 25}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.post("/analyze")
def analyze(body: dict, user=Depends(get_current_user)):
    uid       = user["user_id"]
    base      = user["base_currency"]
    cf        = month_cashflow(uid)
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
