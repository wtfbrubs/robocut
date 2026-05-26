{{- define "clipbot.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "clipbot.labels" -}}
app.kubernetes.io/name: {{ include "clipbot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
