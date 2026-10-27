const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

tg.setHeaderColor('#050202');
tg.setBackgroundColor('#050202');

const BACKEND_URL = "https://mizze-key-bot.onrender.com"; // Thay link Render của bạn vào đây

const userId = tg.initDataUnsafe?.user?.id;
let currentPass = 0;
let requiredPasses = 4; // Mặc định gói 6h là 4 link
let currentPlanParam = "6h";
let collectedPasses = [];
let SHORT_LINKS = [];

// Tải danh sách link từ Backend khi mở app
async function fetchLinks() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/get_links`);
        const data = await res.json();
        if (data.status === "success") {
            SHORT_LINKS = data.links;
        }
    } catch (e) {
        console.error("Không tải được danh sách link:", e);
    }
}
fetchLinks();

function selectPlan(type, passes) {
    if (currentPass > 0 && currentPass < requiredPasses) {
        tg.showAlert("Bạn đang làm dở tiến trình vượt link. Hãy hoàn thành nốt!");
        return;
    }
    currentPass = 0;
    collectedPasses = [];
    requiredPasses = passes;
    currentPlanParam = type;
    
    if (type === '6h') {
        document.getElementById('plan-6h').classList.add('active');
        document.getElementById('plan-3h').classList.remove('active');
    } else {
        document.getElementById('plan-3h').classList.add('active');
        document.getElementById('plan-6h').classList.remove('active');
    }
    updateProgress();
}

async function startEarn() {
    if (!userId) {
        tg.showAlert("Lỗi: Không tìm thấy ID Telegram. Hãy mở qua Bot!");
        return;
    }

    if (currentPass >= requiredPasses) {
        tg.showAlert("Đang xác thực và tạo Key...");
        claimKeyFromBackend();
        return;
    }
    
    try {
        const res = await fetch(`${BACKEND_URL}/get_pass?user_id=${userId}`);
        const data = await res.json();
        
        if (data.status === "success") {
            collectedPasses.push(data.pass_token);
            
            let linkToOpen = SHORT_LINKS[currentPass] || "https://link4m.co/";
            tg.openLink(linkToOpen);
            
            currentPass++;
            updateProgress();
            
            if (currentPass === requiredPasses) {
                tg.showAlert(`🎉 Bạn đã vượt đủ ${requiredPasses} link!\nHãy bấm nút 'BẮT ĐẦU VƯỢT LINK' thêm 1 lần nữa để nhận Key!`);
            } else {
                tg.showAlert(`Đã ghi nhận ${currentPass}/${requiredPasses} lượt.`);
            }
        } else {
            tg.showAlert("Lỗi khi lấy vé từ Server.");
        }
    } catch (error) {
        tg.showAlert("Lỗi kết nối Backend. Vui lòng thử lại!");
    }
}

async function claimKeyFromBackend() {
    try {
        const tokensString = collectedPasses.join(",");
        const res = await fetch(`${BACKEND_URL}/claim_key?user_id=${userId}&plan=${currentPlanParam}&tokens=${tokensString}`, {
            method: 'POST'
        });
        
        const data = await res.json();
        
        if (res.ok && data.status === "success") {
            tg.showAlert(`✅ ĐÃ CÓ KEY!\n\n🔑 Key: ${data.key}\n⏳ Hết hạn: ${data.expires}`);
            currentPass = 0;
            collectedPasses = [];
            updateProgress();
        } else {
            tg.showAlert(`❌ Lỗi: ${data.detail || "Không thể lấy Key"}`);
        }
    } catch (error) {
        tg.showAlert("Lỗi kết nối khi lấy Key!");
    }
}

function updateProgress() {
    const bar = document.getElementById("progress-bar");
    if (bar) {
        const percent = (currentPass / requiredPasses) * 100;
        bar.style.width = percent + "%";
        bar.innerText = `${currentPass} / ${requiredPasses}`;
    }
}

function contactAdmin(planName) {
    tg.showConfirm(`Bạn muốn mua "${planName}"?`, (confirmed) => {
        if (confirmed) {
            tg.openTelegramLink(`https://t.me/lebindz`);
            tg.close();
        }
    });
}

updateProgress();