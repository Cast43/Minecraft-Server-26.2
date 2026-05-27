let activeUploads = 0;
let last_tree_view = "";
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function uploadChunk(file, url, chunk, start, end, chunk_hash, totalChunks, type, path, fileId, i, file_num, updateProgressBar) {
    return fetch(url, {
        method: 'POST',
        body: chunk,
        headers: {
            'Content-Range': `bytes ${start}-${end - 1}/${file.size}`,
            'Content-Length': chunk.size,
            'fileSize': file.size,
            'chunkHash': chunk_hash,
            'chunked': true,
            'type': type,
            'totalChunks': totalChunks,
            'fileName': file.name,
            'location': path,
            'fileId': fileId,
            'chunkId': i,
        },
    })
        .then(async response => {
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(JSON.stringify(errorData) || 'Unknown error occurred');
            }
            return response.json(); // Return the JSON data
        })
        .then(data => {
            if (data.status !== "completed" && data.status !== "partial") {
                throw new Error(data.message || 'Unknown error occurred');
            }
            // Update progress bar
            const progress = (i + 1) / totalChunks * 100;
            updateProgressBar(Math.round(progress), type, file_num, fileId);
        });
}

async function uploadFile(type, file = null, path = null, file_num = 0, fileId = null, _onProgress = null) {
    if (file == null) {
        try {
            file = $("#file")[0].files[0];
        } catch {
            bootbox.alert("Please select a file first.");
            return;
        }
    }
    if (!fileId) {
        fileId = uuidv4();
    }
    const token = getCookie("_xsrf");
    if (type !== "server_upload") {
        document.getElementById("upload_input").innerHTML = '<div class="progress" style="width: 100%;"><div id="upload-progress-bar" class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" aria-valuenow="100" aria-valuemin="0" aria-valuemax="100" style="width: 100%">&nbsp;<i class="ph-bold ph-spinner-gap"></i></div></div>';
    }

    let url = '';
    if (type === "server_upload") {
        url = `/api/v2/servers/${serverId}/files/upload/`;
    } else if (type === "background") {
        url = `/api/v2/crafty/admin/upload/`;
    } else if (type === "import") {
        url = `/api/v2/servers/import/upload/`;
    }
    console.log(url);

    const chunkSize = 1024 * 1024 * 10; // 10MB
    const totalChunks = Math.ceil(file.size / chunkSize);

    const errors = [];
    const batchSize = 30; // Number of chunks to upload in each batch

    try {
        let res = await fetch(url, {
            method: 'POST',
            headers: {
                'X-XSRFToken': token,
                'chunked': true,
                'fileSize': file.size,
                'type': type,
                'totalChunks': totalChunks,
                'fileName': file.name,
                'location': path,
                'fileId': fileId,
            },
            body: null,
        });

        if (!res.ok) {
            let errorResponse = await res.json();
            throw new Error(JSON.stringify(errorResponse));
        }

        let responseData = await res.json();

        if (responseData.status !== "ok") {
            throw new Error(JSON.stringify(responseData));
        }

        const upload_ready_promise = new Promise(resolve => {
            const interval = setInterval(() => {
                if (activeUploads < 2) { // Do not overload browser
                    clearInterval(interval);
                    resolve();
                }
            }, 100);
        });

        await upload_ready_promise;
        activeUploads++;
        for (let i = 0; i < totalChunks; i += batchSize) {
            const batchPromises = [];

            for (let j = 0; j < batchSize && (i + j) < totalChunks; j++) {
                const start = (i + j) * chunkSize;
                const end = Math.min(start + chunkSize, file.size);
                const chunk = file.slice(start, end);
                const chunk_hash = await calculateFileHash(chunk);

                const uploadPromise = uploadChunk(file, url, chunk, start, end, chunk_hash, totalChunks, type, path, fileId, i + j, file_num, updateProgressBar)
                    .catch(error => {
                        errors.push(error); // Store the error
                    });

                batchPromises.push(uploadPromise);
            }

            // Wait for the current batch to complete before proceeding to the next batch
            await Promise.all(batchPromises);

            // Optional delay between batches to account for rate limiting
            await delay(2000); // Adjust the delay time (in milliseconds) as needed
        }
    } catch (error) {
        errors.push(error); // Store the error
    }

    if (errors.length > 0) {
        const errorMessage = errors.map(error => JSON.parse(error.message).data.message || 'Unknown error occurred').join('<br>');
        console.log(errorMessage);
        bootbox.alert({
            title: 'Error',
            message: errorMessage,
            callback: function () {
                window.location.reload();
            },
        });
    } else if (type !== "server_upload") {
        // All promises resolved successfully
        $("#upload_input").html(`<div class="card-header header-sm d-flex justify-content-between align-items-center" style="width: 100%;"><input value="${file.name}" type="text" id="file-uploaded" disabled></input> 🔒</div>`);
        if (type === "import") {
            document.getElementById("lower_half").classList.remove("d-none");
            document.getElementById("lower_half").hidden = false;
            $("#root_upload_button").click();
        } else if (type === "background") {
            setTimeout(function () {
                location.href = `/panel/custom_login`;
            }, 2000);
        }
    } else {

        $(`#upload-progress-bar-${fileId}`).removeClass("progress-bar-striped");
        $(`#upload-progress-bar-${fileId}`).addClass("bg-success");
        $(`#upload-progress-bar-${fileId}`).html('<i style="color: black;" class="ph ph-box-check"></i>');
        removeProgressItem(fileId);

        if (activeUploads == 1) {
            getTreeView($("#table-nav").attr("data-cur-path"));
        }
    }
    activeUploads--;
}

async function calculateFileHash(file) {
    const arrayBuffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

    return hashHex;
}

function updateProgressBar(progress, type, _i, file_id) {
    if (type !== "server_upload") {
        if (progress === 100) {
            $(`#upload-progress-bar`).removeClass("progress-bar-striped")

            $(`#upload-progress-bar`).removeClass("progress-bar-animated")
        }
        $(`#upload-progress-bar`).css('width', progress + '%');
        $(`#upload-progress-bar`).html(progress + '%');
    } else {
        if (progress === 100) {
            $(`#upload-progress-bar-${file_id}`).removeClass("progress-bar-striped")

            $(`#upload-progress-bar-${file_id}`).removeClass("progress-bar-animated")
        }
        $(`#upload-progress-bar-${file_id}`).css('width', progress + '%');
        $(`#upload-percent-${file_id}`).html(progress + '%');
        $("#operation-total").html(`<span id="notif-count" class="badge bg-primary">${$("#upload-progress-bar-parent").children().length}</span>`);
    }
}


function removeProgressItem(item_id) {
    $(`#upload-progress-bar-${item_id}-container`).remove();
    const total_items = $("#upload-progress-bar-parent").children().length
    if (total_items > 0) {
        $("#operation-total").html(`<span id="notif-count" class="badge bg-primary">${total_items}</span>`);
    } else {
        $("#operation-total").html(``); //remove badge if no items
    }
}

function uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replaceAll(/[xy]/g, function (c) {
        const r = Math.trunc(Math.random() * 16),
            v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}


if (webSocket) {
    webSocket.on('upload_process', function (data) {
        if (data.total_files === data.cur_file) {
            updateProgressBar(100, data.type, data.cur_file, data.file_id)
        } else {
            let progress = Math.round((data.cur_file / data.total_files) * 100, 1);
            updateProgressBar(progress, data.type, data.cur_file, data.file_id)
        }
    });
}
globalThis.addEventListener('beforeunload', (e) => {
    console.log(activeUploads)
    if (activeUploads > 0) {
        e.preventDefault();
        globalThis.alert('Uploads active. Are you sure you want to leave?');
    }
});