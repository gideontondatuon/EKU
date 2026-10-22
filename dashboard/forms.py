from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.permissions import PERMISSIONS
from cashflow.models import CashflowTransaction
from core.models import Bank, Denomination, ServiceRegion, SystemSettings, default_menus


class TransactionForm(forms.ModelForm):
    reason = forms.CharField(
        label="Alasan pencatatan / perubahan",
        widget=forms.Textarea(attrs={"rows": 2}),
        min_length=5,
    )
    expected_revision = forms.IntegerField(widget=forms.HiddenInput, required=False)
    is_demo = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput,
        initial=False,
    )

    class Meta:
        model = CashflowTransaction
        fields = [
            "transaction_date",
            "bank",
            "region",
            "denomination",
            "money_type",
            "transaction_type",
            "account",
            "inflow_amount",
            "outflow_amount",
            "pieces",
            "is_demo",
        ]
        widgets = {"transaction_date": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "transaction_date": "Tanggal transaksi",
            "bank": "Bank",
            "region": "Wilayah layanan",
            "denomination": "Pecahan terverifikasi",
            "money_type": "Jenis uang",
            "transaction_type": "Jenis transaksi",
            "account": "Rekening (akses internal terbatas)",
            "inflow_amount": "Inflow (Rupiah utuh)",
            "outflow_amount": "Outflow (Rupiah utuh)",
            "pieces": "Jumlah lembar / keping",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["denomination"].queryset = Denomination.objects.filter(verified=True)
        if not self.instance._state.adding:
            self.fields["expected_revision"].initial = self.instance.revision_number
            self.fields["is_demo"].disabled = True


class ImportForm(forms.Form):
    file = forms.FileField(
        label="File Excel SETBAY (.xlsx)",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}),
    )
    mode = forms.ChoiceField(
        label="Cara memperbarui data",
        initial="ADD",
        choices=[
            ("ADD", "Tambah data baru"),
            ("UPDATE", "Perbarui transaksi terpilih"),
            ("REPLACE", "Ganti snapshot periode / wilayah"),
        ],
    )
    is_demo = forms.BooleanField(required=False, widget=forms.HiddenInput, initial=False)
    full_snapshot_confirmed = forms.BooleanField(
        label="Saya menyatakan sumber ini snapshot lengkap dalam cakupan di bawah", required=False
    )
    start = forms.DateField(
        label="Awal cakupan (untuk snapshot)",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end = forms.DateField(
        label="Akhir cakupan (untuk snapshot)",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    region_codes = forms.CharField(
        label="Kode wilayah dalam snapshot",
        required=False,
        help_text="Pisahkan dengan koma. Gunakan kode sumber, misalnya MANADO atau kode SKM dari master. Nol awal tetap dipertahankan.",
    )

    def clean(self):
        data = super().clean()
        if data.get("mode") == "REPLACE" and not data.get("full_snapshot_confirmed"):
            raise ValidationError("Snapshot lengkap harus dikonfirmasi untuk mengganti periode.")
        if data.get("full_snapshot_confirmed"):
            if not all(data.get(k) for k in ("start", "end", "region_codes")):
                raise ValidationError("Isi tanggal awal, akhir, dan kode wilayah snapshot.")
            if data["start"] > data["end"]:
                raise ValidationError("Tanggal awal harus sebelum/sama dengan akhir.")
        return data

    def scope(self):
        d = self.cleaned_data
        if not d.get("full_snapshot_confirmed"):
            return None
        return {
            "start": d["start"].isoformat(),
            "end": d["end"].isoformat(),
            "region_codes": [v.strip() for v in d["region_codes"].split(",") if v.strip()],
        }


class ReviewForm(forms.Form):
    decision = forms.ChoiceField(
        label="Keputusan",
        choices=[
            ("DEFER", "Tunda untuk memperoleh bukti"),
            ("SKIP_AS_EXISTING", "Lewati sebagai transaksi yang sudah ada"),
            ("CREATE_NEW", "Konfirmasi sebagai transaksi baru"),
            ("UPDATE_SELECTED_EXISTING", "Perbarui UUID transaksi terpilih"),
        ],
    )
    target_id = forms.UUIDField(
        label="UUID transaksi target",
        required=False,
        help_text="Wajib untuk melewati sebagai existing atau memperbarui. Salin UUID dari kandidat yang telah diverifikasi.",
    )
    reason = forms.CharField(
        label="Alasan dan bukti verifikasi", min_length=5, widget=forms.Textarea(attrs={"rows": 3})
    )
    correction_denomination = forms.ModelChoiceField(
        label="Koreksi mapping pecahan (opsional)",
        queryset=Denomination.objects.none(),
        required=False,
    )
    correction_account = forms.CharField(
        label="Nomor rekening yang benar",
        required=False,
        max_length=80,
        help_text="Isi sesuai sumber, termasuk nol di depan. Wajib jika rekening Excel tersimpan sebagai angka.",
    )
    correction_pieces = forms.IntegerField(
        label="Koreksi jumlah lembar / keping (opsional)", min_value=1, required=False
    )
    confirmation_token = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["correction_denomination"].queryset = Denomination.objects.filter(verified=True)

    def clean(self):
        data = super().clean()
        if data.get("decision") in (
            "SKIP_AS_EXISTING",
            "UPDATE_SELECTED_EXISTING",
        ) and not data.get("target_id"):
            self.add_error("target_id", "Pilih UUID target secara eksplisit.")
        return data

    def corrections(self):
        data, result = self.cleaned_data, {}
        if data.get("correction_denomination"):
            denom = data["correction_denomination"]
            result.update(denomination_code=denom.code, denomination_value=str(denom.value))
        if data.get("correction_account"):
            result["account"] = data["correction_account"]
        if data.get("correction_pieces"):
            result["pieces"] = str(data["correction_pieces"])
        return result


class PublicationForm(forms.Form):
    reason = forms.CharField(
        label="Alasan publikasi", min_length=5, widget=forms.Textarea(attrs={"rows": 2})
    )
    is_demo = forms.BooleanField(
        label="Publikasikan DATA DUMMY (hanya evaluasi lokal / staging)", required=False
    )
    confirm = forms.BooleanField(label="Saya telah meninjau data dan cakupan publikasi")


class SettingsForm(forms.ModelForm):
    public_menus = forms.MultipleChoiceField(
        label="Menu publik yang ditampilkan",
        choices=list(
            zip(default_menus(), ["Ringkasan", "Tren", "Pecahan", "Pola Musiman", "Estimasi"])
        ),
        widget=forms.CheckboxSelectMultiple,
    )
    reason = forms.CharField(label="Alasan perubahan pengaturan", min_length=5)

    class Meta:
        model = SystemSettings
        fields = [
            "publication_mode",
            "publication_approval_reference",
            "public_dimensions_approved",
            "automatic_estimation_enabled",
            "public_menus",
        ]
        labels = {
            "publication_mode": "Mode publikasi",
            "publication_approval_reference": "Referensi persetujuan resmi publikasi data operasional",
            "public_dimensions_approved": "Persetujuan mencakup rincian pecahan dan jenis uang",
            "automatic_estimation_enabled": "Tampilkan modul estimasi otomatis di admin",
        }
        help_texts = {
            "publication_approval_reference": "Kosong = publikasi data operasional ditutup. Isi hanya setelah memperoleh persetujuan yang nyata.",
            "automatic_estimation_enabled": "Hanya visibilitas modul; tanpa metode disahkan, tidak menjalankan prediksi.",
        }

    def clean(self):
        data = super().clean()
        if (
            data.get("public_dimensions_approved")
            and not data.get("publication_approval_reference", "").strip()
        ):
            self.add_error(
                "publication_approval_reference",
                "Rincian tambahan memerlukan referensi persetujuan.",
            )
        return data


class UserAccessForm(forms.ModelForm):
    role = forms.ChoiceField(
        label="Peran", choices=[("ADMIN_STAFF", "Admin Staf"), ("SUPER_ADMIN", "Super Admin")]
    )
    permissions = forms.MultipleChoiceField(
        label="Izin individual Admin Staf",
        choices=[],
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    password = forms.CharField(
        label="Kata sandi baru",
        widget=forms.PasswordInput,
        required=False,
        help_text="Minimal 12 karakter. Saat mengedit, kosongkan untuk mempertahankan kata sandi.",
    )
    reason = forms.CharField(label="Alasan perubahan akses", min_length=5)

    class Meta:
        model = get_user_model()
        fields = ["username", "email", "first_name", "last_name", "is_active"]
        labels = {
            "username": "Username",
            "email": "Email",
            "first_name": "Nama depan",
            "last_name": "Nama belakang",
            "is_active": "Akun aktif",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        perms = Permission.objects.filter(
            content_type__app_label="cashflow", codename__in=PERMISSIONS
        )
        self.fields["permissions"].choices = [(p.codename, p.name) for p in perms]
        if self.instance.pk:
            self.fields["role"].initial = (
                "SUPER_ADMIN" if self.instance.is_superuser else "ADMIN_STAFF"
            )
            self.fields["permissions"].initial = list(
                self.instance.user_permissions.values_list("codename", flat=True)
            )

    def clean(self):
        data = super().clean()
        password = data.get("password")
        if not self.instance.pk and not password:
            self.add_error("password", "Kata sandi wajib untuk akun baru.")
        if password:
            validate_password(password, self.instance)
        return data


class BankForm(forms.ModelForm):
    reason = forms.CharField(label="Alasan / bukti sumber", min_length=5)

    class Meta:
        model = Bank
        fields = ["code", "name", "aliases"]
        labels = {"code": "Kode bank", "name": "Nama bank", "aliases": "Alias nama (daftar JSON)"}


class RegionForm(forms.ModelForm):
    reason = forms.CharField(label="Alasan / bukti sumber", min_length=5)

    class Meta:
        model = ServiceRegion
        fields = ["code", "name", "kind"]
        labels = {"code": "Kode sumber wilayah", "name": "Nama wilayah", "kind": "Jenis layanan"}


class DenominationForm(forms.ModelForm):
    reason = forms.CharField(label="Alasan / bukti sumber", min_length=5)

    class Meta:
        model = Denomination
        fields = ["code", "value", "verified", "source_note"]
        labels = {
            "code": "Kode pecahan",
            "value": "Nilai pecahan (Rupiah)",
            "verified": "Mapping diverifikasi dari sumber resmi",
            "source_note": "Referensi verifikasi",
        }
