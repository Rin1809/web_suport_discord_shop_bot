document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('config-form');

    function parseDiscordContent(text) {
        if (!text) return '';

        // emoji
        let html = text.replace(/<a?:(\w+):(\d+)>/g, (match, name, id) => {
            const url = `https://cdn.discordapp.com/emojis/${id}.${match.startsWith('<a:') ? 'gif' : 'png'}?size=48&quality=lossless`;
            return `<img class="discord-emoji" src="${url}" alt=":${name}:">`;
        });
        
        // markdown
        html = marked.parse(html, { gfm: true, breaks: true, mangle: false, headerIds: false });
        
        // xoa the <p> thua
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

    // logic xem truoc embed
    const previewContainer = document.getElementById('embed-preview-container');
    if (previewContainer) {
        const titleInput = document.querySelector('input[name="MESSAGES[SHOP_EMBED_TITLE]"]');
        const descriptionInput = document.querySelector('textarea[name="MESSAGES[SHOP_EMBED_DESCRIPTION]"]');
        const thumbnailInput = document.querySelector('input[name="SHOP_EMBED_THUMBNAIL_URL"]');
        const imageInput = document.querySelector('input[name="SHOP_EMBED_IMAGE_URL"]');
        const footerInput = document.querySelector('input[name="FOOTER_MESSAGES[SHOP_PANEL]"]');
        const colorInput = document.querySelector('input[name="EMBED_COLOR"]');

        const previewRoot = document.getElementById('discord-embed-preview');
        const previewTitle = document.getElementById('preview-title');
        const previewDescription = document.getElementById('preview-description');
        const previewThumbnailImg = document.getElementById('preview-thumbnail');
        const previewImageImg = document.getElementById('preview-image');
        const previewFooter = document.getElementById('preview-footer');

        const updateEmbedPreview = () => {
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
            
            if (thumbUrl) {
                previewThumbnailImg.src = thumbUrl;
                previewThumbnailImg.style.display = 'block';
            } else {
                previewThumbnailImg.style.display = 'none';
            }

            if (imageUrl) {
                previewImageImg.src = imageUrl;
                previewImageImg.style.display = 'block';
            } else {
                previewImageImg.style.display = 'none';
            }
        };

        [titleInput, descriptionInput, thumbnailInput, imageInput, footerInput, colorInput].forEach(input => {
            if (input) {
                input.addEventListener('input', updateEmbedPreview);
                input.addEventListener('change', updateEmbedPreview);
            }
        });
        
        updateEmbedPreview();
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
    document.getElementById('qna-container').appendChild(clone);
}