// رفع الشعار ومعاينته
document.getElementById('logoFile').addEventListener('change', async function(e) {
    const file = this.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('logo', file);
    
    try {
        const response = await fetch('/upload_logo', { method: 'POST', body: formData });
        const data = await response.json();
        if (data.path) {
            // تخزين المسار في حقل مخفي أو في متغير
            window._logoPath = data.path;
            alert('✅ تم رفع الشعار بنجاح!');
        } else {
            alert('❌ فشل الرفع: ' + data.error);
        }
    } catch(e) {
        alert('خطأ في الاتصال');
    }
});

// معاينة الشعار
document.getElementById('previewBtn').addEventListener('click', async function() {
    const source = document.getElementById('sourceUrl').value;
    if (!source) {
        alert('الرجاء إدخال رابط المصدر أولاً');
        return;
    }
    
    const logoPath = window._logoPath || null;
    const position = document.getElementById('logoPosition').value;
    const scale = parseFloat(document.getElementById('logoScale').value) / 100;
    
    const payload = {
        source: source,
        logo_settings: logoPath ? {
            path: logoPath,
            position: position,
            scale: scale
        } : null
    };
    
    const container = document.getElementById('previewContainer');
    const img = document.getElementById('previewImage');
    const error = document.getElementById('previewError');
    
    container.style.display = 'block';
    img.style.display = 'none';
    error.textContent = '⏳ جاري تحميل المعاينة...';
    
    try {
        const response = await fetch('/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        
        if (data.preview) {
            img.src = data.preview;
            img.style.display = 'block';
            error.textContent = '';
        } else {
            error.textContent = '❌ ' + (data.error || 'تعذر الحصول على المعاينة. تأكد من صحة المصدر.');
            img.style.display = 'none';
        }
    } catch(e) {
        error.textContent = '❌ خطأ في الشبكة';
    }
});

// إضافة / تشغيل القناة
document.getElementById('channelForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const key = document.getElementById('streamKey').value;
    const source = document.getElementById('sourceUrl').value;
    const logoPath = window._logoPath || null;
    
    if (!key || !source) {
        alert('المفتاح والمصدر مطلوبان');
        return;
    }
    
    const videoSettings = {
        resolution: document.getElementById('resolution').value,
        fps: parseInt(document.getElementById('fps').value),
        bitrate: document.getElementById('videoBitrate').value,
        codec: document.getElementById('videoCodec').value
    };
    
    const audioSettings = {
        bitrate: document.getElementById('audioBitrate').value,
        sample_rate: parseInt(document.getElementById('sampleRate').value),
        channels: parseInt(document.getElementById('audioChannels').value),
        codec: 'aac'
    };
    
    const logoSettings = logoPath ? {
        path: logoPath,
        position: document.getElementById('logoPosition').value,
        scale: parseFloat(document.getElementById('logoScale').value) / 100
    } : null;
    
    const payload = {
        key: key,
        source: source,
        action: 'start',
        video: videoSettings,
        audio: audioSettings,
        logo: logoSettings
    };
    
    try {
        const response = await fetch('/channel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (data.status === 'started') {
            alert('✅ تم تشغيل البث بنجاح!');
        } else {
            alert('❌ حدث خطأ: ' + JSON.stringify(data));
        }
    } catch(e) {
        alert('خطأ في الاتصال بالخادم');
    }
});

// جلب الحالة والسجلات بشكل دوري (Polling)
async function fetchStatus() {
    try {
        const response = await fetch('/status');
        const channels = await response.json();
        const container = document.getElementById('channelsStatus');
        
        if (Object.keys(channels).length === 0) {
            container.innerHTML = '<p style="color:#aaa;">لا توجد قنوات مفعلة</p>';
            return;
        }
        
        let html = '';
        for (const [key, data] of Object.entries(channels)) {
            const statusClass = 'status-' + data.status;
            html += `
                <div class="channel-item">
                    <div><span class="key">${key}</span> <span class="status-badge ${statusClass}">${data.status}</span></div>
                    <div style="font-size:0.8rem; color:#8b949e;">المصدر: ${data.source}</div>
                    <div style="font-size:0.8rem; color:#8b949e;">المحاولات: ${data.retries}</div>
                    ${data.preview ? `<img src="${data.preview}" style="max-width:100px; border-radius:4px; margin-top:5px;">` : ''}
                    <div class="channel-actions">
                        <button class="btn btn-danger btn-sm" onclick="stopChannel('${key}')">إيقاف</button>
                        <button class="btn btn-secondary btn-sm" onclick="deleteChannel('${key}')">حذف</button>
                    </div>
                </div>
            `;
        }
        container.innerHTML = html;
    } catch(e) {
        console.error('خطأ في جلب الحالة', e);
    }
}

async function fetchLogs() {
    try {
        const response = await fetch('/logs');
        const logs = await response.json();
        const display = document.getElementById('logsDisplay');
        display.textContent = logs.join('\n') || 'لا توجد سجلات.';
        // تمرير إلى الأسفل
        display.scrollTop = display.scrollHeight;
    } catch(e) {
        console.error('خطأ في جلب السجلات', e);
    }
}

// دوال التحكم
window.stopChannel = async function(key) {
    if (!confirm(`هل تريد إيقاف القناة "${key}"؟`)) return;
    await fetch('/channel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, action: 'stop' })
    });
    fetchStatus();
};

window.deleteChannel = async function(key) {
    if (!confirm(`هل تريد حذف القناة "${key}" نهائيًا؟`)) return;
    await fetch('/channel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, action: 'delete' })
    });
    fetchStatus();
};

// تشغيل التحديثات الدورية (Polling)
setInterval(fetchStatus, 3000); // كل 3 ثوان
setInterval(fetchLogs, 4000);  // كل 4 ثوان

// جلب أولي
fetchStatus();
fetchLogs();