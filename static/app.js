document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('config-form');

    function parseDiscordContent(text) {
        if (!text) return '';

        let html = text.replace(/<a?:(\w+):(\d+)>/g, (match, name, id) => {
            const url = `https://cdn.discordapp.com/emojis/${id}.${match.startsWith('<a:') ? 'gif' : 'png'}?size=48&quality=lossless`;
            return `<img class="discord-emoji" src="${url}" alt=":${name}:">`;
        });
        
        html = marked.parse(html, { gfm: true, breaks: true, mangle: false, headerIds: false });
        
        if (html.startsWith('<p>') && html.endsWith('</p>\n')) {
             html = html.substring(3, html.length - 5);
        }

        return html;
    }

    // logic tab
    const tabContainer = document.getElementById('configTabs');
    if (tabContainer) {
        const navLinks = tabContainer.querySelectorAll('.nav-link');
        const tabPanes = document.querySelectorAll('.tab-content .tab-pane');

        navLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                navLinks.forEach(l => l.classList.remove('active'));
                this.classList.add('active');
                tabPanes.forEach(p => p.classList.remove('active'));
                const targetPane = document.querySelector(this.getAttribute('data-target'));
                if (targetPane) {
                    targetPane.classList.add('active');
                }
            });
        });
    }

    // mo rong textarea
    document.body.addEventListener('click', function(event) {
        const target = event.target;
        if (target.classList.contains('expand-toggle-btn')) {
            event.preventDefault(); 
            const wrapper = target.closest('.textarea-wrapper');
            if (wrapper) {
                const textarea = wrapper.querySelector('textarea');
                const isExpanded = wrapper.classList.toggle('expanded');
                target.textContent = isExpanded ? '−' : '+';
                if (isExpanded) {
                    textarea.style.height = 'auto';
                    textarea.style.height = (textarea.scrollHeight + 5) + 'px';
                } else {
                    textarea.style.height = ''; 
                }
            }
        }
    });

    // logic dual-list
    const availableRolesSelect = document.getElementById('available-roles');
    const selectedRolesSelect = document.getElementById('selected-roles');
    const addBtn = document.getElementById('add-role-btn');
    const removeBtn = document.getElementById('remove-role-btn');

    function moveOptions(source, destination) {
        Array.from(source.selectedOptions).forEach(option => {
            destination.appendChild(option);
        });
    }

    if (addBtn) addBtn.addEventListener('click', () => moveOptions(availableRolesSelect, selectedRolesSelect));
    if (removeBtn) removeBtn.addEventListener('click', () => moveOptions(selectedRolesSelect, availableRolesSelect));
    if(availableRolesSelect) availableRolesSelect.addEventListener('dblclick', () => moveOptions(availableRolesSelect, selectedRolesSelect));
    if(selectedRolesSelect) selectedRolesSelect.addEventListener('dblclick', () => moveOptions(selectedRolesSelect, availableRolesSelect));

    if (form) {
        form.addEventListener('submit', function() {
            if(selectedRolesSelect) {
                for (const option of selectedRolesSelect.options) {
                    option.selected = true;
                }
            }
        });
    }

    // active link sidebar
    const sidebarLinks = document.querySelectorAll('.sidebar-nav a');
    const path = window.location.pathname;
    const guildId = document.body.dataset.guildId;

    sidebarLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href && href !== '#' && path.includes(href)) {
             sidebarLinks.forEach(btn => btn.classList.remove('active'));
             link.classList.add('active');
        }
    });
    
    if (path.includes(`/edit/${guildId}`) && !path.includes('/member/') && !path.includes('/history')) {
        const configLink = document.querySelector(`.sidebar-nav a[href*="/edit/${guildId}"]`);
         if(configLink && !configLink.href.includes('member') && !configLink.href.includes('history')) {
            sidebarLinks.forEach(btn => btn.classList.remove('active'));
            configLink.classList.add('active');
        }
    }

    // khoi tao color picker
    if (window.Coloris) {
        Coloris({
            themeMode: 'dark',
            alpha: false,
            el: '[data-coloris]',
        });
    }

    const colorInput = document.querySelector('input[name="EMBED_COLOR"]');

    // xem truoc embed shop
    const shopPreviewContainer = document.getElementById('shop-embed-preview-container');
    if (shopPreviewContainer) {
        const titleInput = document.querySelector('input[name="MESSAGES[SHOP_EMBED_TITLE]"]');
        const descriptionInput = document.querySelector('textarea[name="MESSAGES[SHOP_EMBED_DESCRIPTION]"]');
        const thumbnailInput = document.querySelector('input[name="SHOP_EMBED_THUMBNAIL_URL"]');
        const imageInput = document.querySelector('input[name="SHOP_EMBED_IMAGE_URL"]');
        const footerInput = document.querySelector('input[name="FOOTER_MESSAGES[SHOP_PANEL]"]');

        const previewRoot = document.getElementById('discord-shop-embed-preview');
        const previewTitle = document.getElementById('preview-shop-title');
        const previewDescription = document.getElementById('preview-shop-description');
        const previewThumbnailImg = document.getElementById('preview-shop-thumbnail');
        const previewImageImg = document.getElementById('preview-shop-image');
        const previewFooter = document.getElementById('preview-shop-footer');

        const updateShopEmbedPreview = () => {
            const title = titleInput.value;
            const description = descriptionInput.value;
            const thumbUrl = thumbnailInput.value;
            const imageUrl = imageInput.value;
            const footer = footerInput.value;
            const color = colorInput.value || '#ff00af';
            
            previewTitle.innerHTML = parseDiscordContent(title);
            previewDescription.innerHTML = parseDiscordContent(description);
            previewFooter.innerHTML = parseDiscordContent(footer);
            previewRoot.style.borderColor = color;
            
            previewThumbnailImg.style.display = thumbUrl ? 'block' : 'none';
            if(thumbUrl) previewThumbnailImg.src = thumbUrl;
           
            previewImageImg.style.display = imageUrl ? 'block' : 'none';
            if(imageUrl) previewImageImg.src = imageUrl;
        };

        [titleInput, descriptionInput, thumbnailInput, imageInput, footerInput, colorInput].forEach(input => {
            if (input) input.addEventListener('input', updateShopEmbedPreview);
        });
        updateShopEmbedPreview();
    }

    // xem truoc embed tai khoan
    const accountPreviewContainer = document.getElementById('account-embed-preview-container');
    if(accountPreviewContainer) {
        const titleInput = document.querySelector('input[name="MESSAGES[ACCOUNT_INFO_TITLE]"]');
        const descInput = document.querySelector('textarea[name="MESSAGES[ACCOUNT_INFO_DESC]"]');
        const fieldNameInput = document.querySelector('input[name="MESSAGES[BALANCE_FIELD_NAME]"]');
        const fieldValueInput = document.querySelector('input[name="MESSAGES[BALANCE_FIELD_VALUE]"]');
        const footerInput = document.querySelector('input[name="FOOTER_MESSAGES[ACCOUNT_INFO]"]');
        
        const previewRoot = document.getElementById('discord-account-embed-preview');
        const previewTitle = document.getElementById('preview-account-title');
        const previewDesc = document.getElementById('preview-account-description');
        const previewFieldName = document.getElementById('preview-account-field-name');
        const previewFieldValue = document.getElementById('preview-account-field-value');
        const previewFooter = document.getElementById('preview-account-footer');

        const updateAccountEmbedPreview = () => {
            previewRoot.style.borderColor = colorInput.value || '#ff00af';
            previewTitle.innerHTML = parseDiscordContent(titleInput.value);
            previewDesc.innerHTML = parseDiscordContent(descInput.value);
            previewFieldName.innerHTML = parseDiscordContent(fieldNameInput.value);
            previewFieldValue.innerHTML = parseDiscordContent(fieldValueInput.value.replace('{balance}', '9,999'));
            previewFooter.innerHTML = parseDiscordContent(footerInput.value);
        };
        
        [titleInput, descInput, fieldNameInput, fieldValueInput, footerInput, colorInput].forEach(input => {
            if(input) input.addEventListener('input', updateAccountEmbedPreview);
        });
        updateAccountEmbedPreview();
    }

    // xem truoc embed ty le dao coin
    const ratesPreviewContainer = document.getElementById('rates-embed-preview-container');
    if(ratesPreviewContainer) {
        const titleInput = document.querySelector('input[name="MESSAGES[EARNING_RATES_TITLE]"]');
        const imageInput = document.querySelector('input[name="EARNING_RATES_IMAGE_URL"]');
        const descInput = document.querySelector('textarea[name="MESSAGES[EARNING_RATES_DESC]"]');
        const boosterInput = document.querySelector('textarea[name="MESSAGES[BOOSTER_MULTIPLIER_INFO]"]');
        const footerInput = document.querySelector('input[name="FOOTER_MESSAGES[EARNING_RATES]"]');

        const previewRoot = document.getElementById('discord-rates-embed-preview');
        const previewTitle = document.getElementById('preview-rates-title');
        const previewImage = document.getElementById('preview-rates-image');
        const previewDesc = document.getElementById('preview-rates-description');
        const previewFooter = document.getElementById('preview-rates-footer');

        const updateRatesEmbedPreview = () => {
            const imageUrl = imageInput.value;
            previewRoot.style.borderColor = colorInput.value || '#ff00af';
            previewTitle.innerHTML = parseDiscordContent(titleInput.value);
            previewImage.style.display = imageUrl ? 'block' : 'none';
            if(imageUrl) previewImage.src = imageUrl;
            
            const fullDesc = `${descInput.value}\n\n${boosterInput.value}`;
            previewDesc.innerHTML = parseDiscordContent(fullDesc.trim());
            previewFooter.innerHTML = parseDiscordContent(footerInput.value);
        };

        [titleInput, imageInput, descInput, boosterInput, footerInput, colorInput].forEach(input => {
            if(input) input.addEventListener('input', updateRatesEmbedPreview);
        });
        updateRatesEmbedPreview();
    }

    // logic xem truoc q&a
    const qnaContainer = document.getElementById('qna-container');
    if (qnaContainer) {
        const updateQnAPreview = (qnaRow) => {
            const titleInput = qnaRow.querySelector('input[name="qna_answer_title[]"]');
            const descInput = qnaRow.querySelector('textarea[name="qna_answer_description[]"]');
            const emojiInput = qnaRow.querySelector('input[name="qna_emoji[]"]');
            const previewRoot = qnaRow.querySelector('.discord-embed-preview');
            const previewTitle = qnaRow.querySelector('.preview-qna-title');
            const previewDesc = qnaRow.querySelector('.preview-qna-description');

            if (!previewRoot || !previewTitle || !previewDesc) return;
            
            previewRoot.style.borderColor = colorInput.value || '#ff00af';
            const fullTitle = `${emojiInput.value || ''} ${titleInput.value || ''}`.trim();
            previewTitle.innerHTML = parseDiscordContent(fullTitle);
            previewDesc.innerHTML = parseDiscordContent(descInput.value);
        };
        
        qnaContainer.addEventListener('input', function(event) {
            const qnaRow = event.target.closest('.qna-row');
            if (qnaRow) {
                updateQnAPreview(qnaRow);
            }
        });

        document.querySelectorAll('.qna-row').forEach(updateQnAPreview);
        colorInput.addEventListener('input', () => {
            document.querySelectorAll('.qna-row').forEach(updateQnAPreview);
        });
    }

});

// ham cho dynamic rows
function removeRow(button) { 
    button.closest('.dynamic-row').remove(); 
}
function addShopRole() {
    const template = document.getElementById('shop-role-template');
    const clone = template.content.cloneNode(true);
    document.getElementById('shop-roles-container').appendChild(clone);
    if(window.Coloris) Coloris.update();
}
function addCategoryRate() { 
    const template = document.getElementById('category-rate-template');
    const clone = template.content.cloneNode(true);
    document.getElementById('category-rates-container').appendChild(clone);
}
function addChannelRate() { 
    const template = document.getElementById('channel-rate-template');
    const clone = template.content.cloneNode(true);
    document.getElementById('channel-rates-container').appendChild(clone);
}
function addQnA() { 
    const template = document.getElementById('qna-template');
    const clone = template.content.cloneNode(true);
    const container = document.getElementById('qna-container');
    container.appendChild(clone);
    const newRow = container.lastElementChild;
    const colorInput = document.querySelector('input[name="EMBED_COLOR"]');
    if (newRow) {
        const previewRoot = newRow.querySelector('.discord-embed-preview');
        if (previewRoot) {
            previewRoot.style.borderColor = colorInput.value || '#ff00af';
        }
    }
}