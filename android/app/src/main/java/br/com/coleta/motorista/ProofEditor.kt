package br.com.coleta.motorista

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.view.MotionEvent
import android.view.View
import android.widget.*
import android.text.Editable
import android.text.TextWatcher
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.time.Instant
import java.time.Duration

class SignaturePad(context: Context, saved: JSONArray? = null): View(context) {
    var changed: () -> Unit = {}
    private var strokes= saved ?: JSONArray()
    private var current: JSONArray? = null
    private var pointCount=(0 until strokes.length()).sumOf { strokes.getJSONArray(it).length() }
    private val ink=Paint(Paint.ANTI_ALIAS_FLAG).apply { color=Color.BLACK;style=Paint.Style.STROKE;strokeWidth=3f;strokeCap=Paint.Cap.ROUND;strokeJoin=Paint.Join.ROUND }
    init { setBackgroundColor(Color.WHITE);contentDescription="Área para assinar com o dedo" }
    fun points(): JSONArray = JSONArray(strokes.toString())
    fun clear() { strokes=JSONArray();pointCount=0;current=null;invalidate();changed() }
    fun hasInk(): Boolean {
        for(i in 0 until strokes.length()) {
            val s=strokes.getJSONArray(i)
            for(j in 1 until s.length()) {
                val a=s.getJSONArray(j-1);val b=s.getJSONArray(j)
                if(kotlin.math.abs(a.getDouble(0)-b.getDouble(0))+kotlin.math.abs(a.getDouble(1)-b.getDouble(1))>2) return true
            }
        };return false
    }
    private fun render(canvas: Canvas) {
        canvas.drawColor(Color.WHITE)
        for(i in 0 until strokes.length()) {
            val s=strokes.getJSONArray(i);val path=Path()
            for(j in 0 until s.length()) {
                val p=s.getJSONArray(j)
                if(j==0) path.moveTo(p.getDouble(0).toFloat(),p.getDouble(1).toFloat()) else path.lineTo(p.getDouble(0).toFloat(),p.getDouble(1).toFloat())
            };canvas.drawPath(path,ink)
        }
    }
    override fun onDraw(canvas: Canvas) { super.onDraw(canvas);canvas.save();canvas.scale(width/640f,height/240f);render(canvas);canvas.restore() }
    override fun onTouchEvent(event: MotionEvent): Boolean {
        if(width==0||height==0)return false
        if(event.actionMasked==MotionEvent.ACTION_DOWN) {
            if(strokes.length()>=100||pointCount>=4000)return false
            current=JSONArray();strokes.put(current);parent?.requestDisallowInterceptTouchEvent(true)
        }
        val s=current ?: return false
        if(s.length()<1000 && pointCount<4000) { pointCount++;s.put(JSONArray().put((event.x/width*640).coerceIn(0f,640f).toDouble()).put((event.y/height*240).coerceIn(0f,240f).toDouble())) }
        invalidate()
        if(event.actionMasked==MotionEvent.ACTION_UP||event.actionMasked==MotionEvent.ACTION_CANCEL) {
            current=null;parent?.requestDisallowInterceptTouchEvent(false);changed();performClick()
        };return true
    }
    override fun performClick(): Boolean { super.performClick();return true }
    fun png(): String {
        check(hasInk()) { "Peça ao responsável para assinar ou escolha uma exceção justificada." }
        val bitmap=Bitmap.createBitmap(640,240,Bitmap.Config.ARGB_8888)
        try {
            render(Canvas(bitmap));val out=ByteArrayOutputStream();check(bitmap.compress(Bitmap.CompressFormat.PNG,100,out))
            check(out.size()<=131072) { "Assinatura muito grande. Limpe e refaça." }
            return Base64.encodeToString(out.toByteArray(),Base64.NO_WRAP)
        } finally { bitmap.recycle() }
    }
}

class ProofEditor(context: Context, saved: JSONObject?, private val changed: () -> Unit): LinearLayout(context) {
    private val name=EditText(context).apply { hint="Nome do responsável";filters=arrayOf(android.text.InputFilter.LengthFilter(200));setText(saved?.optString("responsavel") ?: "") }
    private val reason=EditText(context).apply { hint="Motivo da ausência ou recusa";filters=arrayOf(android.text.InputFilter.LengthFilter(1000));setText(saved?.optString("motivo") ?: "") }
    private val mode=Spinner(context)
    private val pad=SignaturePad(context,saved?.optJSONArray("tracos"))
    private var captured=saved?.optString("capturado_em")?.takeIf { it.isNotBlank() } ?: Instant.now().toString()
    init {
        orientation=VERTICAL
        addView(TextView(context).apply { text="Comprovante da coleta";textSize=22f })
        addView(TextView(context).apply { text="O responsável pode assinar abaixo. Em caso de ausência ou recusa, registre o motivo. Quantidades a conferir continuam sujeitas à conferência." })
        mode.adapter=ArrayAdapter(context,android.R.layout.simple_spinner_dropdown_item,listOf("Assinatura","Responsável ausente","Recusa de assinatura"))
        mode.setSelection(listOf("assinatura","ausencia","recusa").indexOf(saved?.optString("tipo") ?: "assinatura").coerceAtLeast(0))
        addView(mode);addView(name);addView(pad,LayoutParams(LayoutParams.MATCH_PARENT,(180*resources.displayMetrics.density).toInt()))
        val clear=Button(context).apply { text="Limpar e refazer rubrica";setOnClickListener { pad.clear() } };addView(clear);addView(reason)
        fun visibility() { val signing=mode.selectedItemPosition==0;pad.visibility=if(signing) VISIBLE else GONE;clear.visibility=pad.visibility;reason.visibility=if(signing) GONE else VISIBLE }
        visibility()
        mode.onItemSelectedListener=object:AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(p:AdapterView<*>?) {}
            override fun onItemSelected(p:AdapterView<*>?,v:View?,position:Int,id:Long) { visibility();changed() }
        }
        pad.changed={captured=Instant.now().toString();changed()}
        val watcher=object:TextWatcher {
            override fun beforeTextChanged(s:CharSequence?,start:Int,count:Int,after:Int) {}
            override fun onTextChanged(s:CharSequence?,start:Int,before:Int,count:Int) {}
            override fun afterTextChanged(s:Editable?) { changed() }
        };name.addTextChangedListener(watcher);reason.addTextChangedListener(watcher)
    }
    fun draft(): JSONObject = JSONObject().put("tipo",listOf("assinatura","ausencia","recusa")[mode.selectedItemPosition])
        .put("responsavel",name.text.toString()).put("motivo",reason.text.toString()).put("capturado_em",captured).put("tracos",pad.points())
    fun proof(): JSONObject {
        val type=listOf("assinatura","ausencia","recusa")[mode.selectedItemPosition]
        val who=name.text.toString().trim();val why=reason.text.toString().trim()
        check(who.length<=200 && why.length<=1000) { "Nome: até 200 caracteres. Motivo: até 1.000." }
        val result=JSONObject().put("tipo",type).put("responsavel",who.ifBlank { null } ?: JSONObject.NULL)
        if(type=="assinatura") {
            check(who.isNotEmpty()) { "Informe o nome do responsável pela rubrica." }
            check(Duration.between(ApiTime.parse(captured),Instant.now()).seconds in 0..1800) { "A rubrica tem mais de 30 minutos. Peça ao responsável para refazê-la." }
            result.put("imagem_png",pad.png()).put("capturado_em",captured)
        } else {
            check(why.isNotEmpty()) { "Justifique a ausência ou recusa de assinatura." }
            result.put("motivo",why).put("capturado_em",Instant.now().toString())
        };return result
    }
}
