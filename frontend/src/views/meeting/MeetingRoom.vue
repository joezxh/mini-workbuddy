<template>
  <div class="meeting-room">
    <!-- 未入会：房间加入表单 -->
    <div v-if="!joined" class="join-panel">
      <a-card title="加入视频会议" :bordered="false">
        <a-form layout="vertical" @submit.prevent="join">
          <a-form-item label="房间号">
            <a-input
              v-model:value="roomInput"
              placeholder="如 project-review-01（字母/数字/-/_，3-64 位）"
              :maxlength="64"
              :disabled="joining"
              @press-enter="join"
            />
          </a-form-item>
          <a-form-item>
            <a-button type="primary" :loading="joining" block @click="join">
              {{ joining ? '连接中…' : '加入会议' }}
            </a-button>
          </a-form-item>
        </a-form>
        <a-alert
          v-if="errorMsg"
          type="error"
          :message="errorMsg"
          show-icon
          style="margin-top: 8px"
        />
      </a-card>
    </div>

    <!-- 已入会：视频网格 + 控制条 -->
    <template v-else>
      <div class="video-grid">
        <!-- 本地画面 -->
        <div class="video-tile">
          <video ref="localVideoRef" autoplay playsinline muted />
          <span class="tile-label">
            {{ selfName }}（我）
            <a-tag v-if="!micOn" color="red">麦已关</a-tag>
            <a-tag v-if="!camOn" color="red">摄像头已关</a-tag>
          </span>
        </div>
        <!-- 远端画面：trackSubscribed 时 attach 到对应容器 -->
        <div
          v-for="p in remoteParticipants"
          :key="p.sid"
          class="video-tile"
        >
          <div :ref="(el) => setRemoteSlot(p.sid, el as HTMLElement | null)" class="remote-slot" />
          <span class="tile-label">
            {{ p.name || p.identity }}
            <a-tag v-if="!p.audioOn" color="red">麦已关</a-tag>
          </span>
        </div>
        <a-empty
          v-if="remoteParticipants.length === 0"
          class="waiting-hint"
          description="等待其他参会者加入…"
        />
      </div>

      <div class="control-bar">
        <a-space>
          <a-tag color="blue">房间 {{ roomName }}</a-tag>
          <a-tag>{{ remoteParticipants.length + 1 }} 人在线</a-tag>
        </a-space>
        <a-space>
          <a-button :danger="!micOn" @click="toggleMic">
            <AudioOutlined v-if="micOn" />
            <AudioMutedOutlined v-else />
            {{ micOn ? '静音' : '取消静音' }}
          </a-button>
          <a-button :danger="!camOn" @click="toggleCam">
            <VideoCameraOutlined />
            {{ camOn ? '关闭摄像头' : '开启摄像头' }}
          </a-button>
          <a-button danger @click="leave">
            <PhoneOutlined :rotate="135" />
            离开会议
          </a-button>
        </a-space>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * 视频会议房间页（LiveKit 自建 SFU）
 *
 * spec: docs/LIVEKIT_SELF_HOSTED_DEPLOYMENT_GUIDE.md §6（前端集成）
 * 流程：createMeetingToken 拿 { ws_url, token } → Room.connect → 本地预览
 *       + 远端 track.attach() 渲染；麦克风/摄像头开关走 setMicrophoneEnabled /
 *       setCameraEnabled（livekit-client 内部管理 getUserMedia 与 renegotiation）。
 * Electron 桌面端需主进程放行 media 权限，见 electron/main/index.ts。
 */
import { nextTick, onBeforeUnmount, ref } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  AudioOutlined,
  AudioMutedOutlined,
  VideoCameraOutlined,
  PhoneOutlined,
} from '@ant-design/icons-vue'
import { Room, RoomEvent, Track } from 'livekit-client'
import { createMeetingToken } from '@/api/meeting'

const route = useRoute()

// ── 入会状态 ────────────────────────────────────────────
const roomInput = ref((route.query.room as string) || '')
const joining = ref(false)
const joined = ref(false)
const errorMsg = ref('')
let room: Room | null = null
const roomName = ref('')
const selfName = ref('')

// ── 设备开关状态 ────────────────────────────────────────
const micOn = ref(true)
const camOn = ref(true)

// 本地预览 video
const localVideoRef = ref<HTMLVideoElement | null>(null)

// 远端参会者（模板渲染用轻量快照，媒体元素由 attach 直接注入 DOM）
interface RemoteSnap {
  sid: string
  identity: string
  name: string
  audioOn: boolean
}
const remoteParticipants = ref<RemoteSnap[]>([])

// 每位远端参会者的视频挂载容器：sid -> HTMLElement
const remoteSlots = new Map<string, HTMLElement>()
// 每位远端参会者已 attach 的媒体元素，卸载时统一 detach
const attachedEls = new Set<HTMLMediaElement>()

function setRemoteSlot(sid: string, el: HTMLElement | null) {
  if (el) remoteSlots.set(sid, el)
  else remoteSlots.delete(sid)
}

/** 从 livekit 参会者对象生成/更新快照 */
function upsertRemoteSnap(p: any) {
  const snap = remoteParticipants.value.find((s) => s.sid === p.sid)
  const audioOn = p.getTrackPublication?.(Track.Source.Microphone)?.isMuted === false
  if (snap) {
    snap.name = p.name || p.identity
    snap.audioOn = audioOn
  } else {
    remoteParticipants.value.push({ sid: p.sid, identity: p.identity, name: p.name || p.identity, audioOn })
  }
}

function removeRemoteSnap(p: any) {
  remoteParticipants.value = remoteParticipants.value.filter((s) => s.sid !== p.sid)
}

/** 把远端 Track 挂到该参会者的容器（video）或隐藏 audio 元素（audio） */
async function onTrackSubscribed(track: Track) {
  await nextTick()
  const participant = (track as any).participant
  const slot = remoteSlots.get(participant?.sid)
  if (track.kind === Track.Kind.Video && slot) {
    const el = track.attach() as HTMLVideoElement
    el.style.width = '100%'
    el.style.height = '100%'
    el.style.objectFit = 'cover'
    slot.appendChild(el)
    attachedEls.add(el)
  } else if (track.kind === Track.Kind.Audio) {
    const el = track.attach() as HTMLAudioElement
    attachedEls.add(el)
    el.play?.().catch(() => {
      /* 自动播放被拦截：本地麦已开，startAudio 后恢复 */
    })
  }
  upsertRemoteSnap(participant)
}

function onTrackUnsubscribed(track: Track) {
  const els = track.detach() as HTMLMediaElement[]
  els.forEach((el) => {
    el.remove()
    attachedEls.delete(el)
  })
}

async function join() {
  const name = roomInput.value.trim()
  if (!name) {
    errorMsg.value = '请输入房间号'
    return
  }
  if (joining.value || joined.value) return
  joining.value = true
  errorMsg.value = ''
  try {
    // 1. 向后端换入会 token（复用工程 JWT 鉴权）
    const tk = await createMeetingToken({ room: name })
    // 2. 连接自建 SFU
    const r = new Room({ adaptiveStream: true, dynacast: true })
    r.on(RoomEvent.TrackSubscribed, onTrackSubscribed)
    r.on(RoomEvent.TrackUnsubscribed, onTrackUnsubscribed)
    r.on(RoomEvent.ParticipantConnected, (p: any) => upsertRemoteSnap(p))
    r.on(RoomEvent.ParticipantDisconnected, (p: any) => removeRemoteSnap(p))
    r.on(RoomEvent.ActiveSpeakersChanged, () => {
      // 快照轻量刷新（麦状态在 trackSubscribed/muted 事件里更新即可）
      if (room) Array.from(room.remoteParticipants.values()).forEach(upsertRemoteSnap as any)
    })
    r.on(RoomEvent.Disconnected, () => {
      if (joined.value) message.warning('与会议服务器断开')
      cleanup()
    })
    await r.connect(tk.ws_url, tk.token)
    // 3. 打开本地麦克风 + 摄像头（getUserMedia 权限在此触发）
    micOn.value = true
    camOn.value = true
    await r.localParticipant.setMicrophoneEnabled(true)
    await r.localParticipant.setCameraEnabled(true)
    // 4. 本地预览：把摄像头 LocalVideoTrack 挂到预览 video（muted 防回声）
    const camPub = r.localParticipant.getTrackPublication(Track.Source.Camera) as any
    const camTrack = camPub?.track as Track | undefined
    if (camTrack && localVideoRef.value) {
      camTrack.attach(localVideoRef.value)
    }
    room = r
    roomName.value = tk.room
    selfName.value = tk.name
    // 已有远端参会者（非首个入会场景）补建快照
    Array.from(r.remoteParticipants.values()).forEach(upsertRemoteSnap as any)
    joined.value = true
  } catch (e: any) {
    // getUserMedia 被拒 / token 失效 / SFU 不可达等均在此收口
    errorMsg.value = String(e?.message ?? e)
    message.error(`入会失败：${errorMsg.value}`)
    room?.disconnect().catch(() => {})
    room = null
    joined.value = false
  } finally {
    joining.value = false
  }
}

async function toggleMic() {
  if (!room) return
  try {
    await room.localParticipant.setMicrophoneEnabled(!micOn.value)
    micOn.value = !micOn.value
  } catch (e: any) {
    message.error(`麦克风操作失败：${e?.message || e}`)
  }
}

async function toggleCam() {
  if (!room) return
  try {
    await room.localParticipant.setCameraEnabled(!camOn.value)
    camOn.value = !camOn.value
  } catch (e: any) {
    message.error(`摄像头操作失败：${e?.message || e}`)
  }
}

function cleanup() {
  room?.disconnect().catch(() => {})
  room = null
  attachedEls.forEach((el) => el.remove())
  attachedEls.clear()
  remoteSlots.clear()
  remoteParticipants.value = []
  joined.value = false
}

function leave() {
  cleanup()
  message.success('已离开会议')
}

onBeforeUnmount(cleanup)
</script>

<style scoped>
.meeting-room {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.join-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 360px;
}

.video-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 12px;
  padding: 12px;
  overflow: auto;
  align-content: start;
  position: relative;
}

.video-tile {
  position: relative;
  background: #14161a;
  border-radius: 8px;
  overflow: hidden;
  aspect-ratio: 16 / 9;
  min-height: 180px;
}

.video-tile video,
.remote-slot,
.remote-slot video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.remote-slot {
  position: absolute;
  inset: 0;
}

.tile-label {
  position: absolute;
  left: 8px;
  bottom: 8px;
  color: #fff;
  font-size: 12px;
  background: rgba(0, 0, 0, 0.45);
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  z-index: 1;
}

.waiting-hint {
  grid-column: 1 / -1;
  color: #999;
  padding: 40px 0;
}

.control-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-top: 1px solid var(--ant-color-border, #303030);
  background: var(--ant-color-bg-container, #141414);
  flex-wrap: wrap;
  gap: 8px;
}
</style>
