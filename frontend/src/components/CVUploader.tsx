import { useT } from "../i18n/LanguageProvider";

type Props = {
  onUpload: (file: File) => void;
  disabled?: boolean;
  label?: string;
};
export function CVUploader({ onUpload, disabled = false, label }: Props) {
  const t = useT();

  return (
    <label className="upload">
      {disabled ? t("shared.parsing") : (label ?? t("shared.uploadCv"))}
      <input
        id="cv-uploader-input"
        disabled={disabled}
        type="file"
        accept=".pdf,.docx,.txt,.md"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file);
          e.currentTarget.value = "";
        }}
      />
    </label>
  );
}
